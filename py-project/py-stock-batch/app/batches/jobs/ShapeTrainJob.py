"""shape_proba 모델을 주말에 재학습하고, 게이트를 통과하면 라이브로 승격하는 배치.

실행
    매주 토요일 02:00 (KST). 금요일 20:00 적재 + 21:40 라벨 확정 이후여야
    그 주 마지막 거래일까지 학습셋에 든다.
    batch_job_master 등록은 sql/20_shape_train_job_register.sql 참고.

파이프라인 3단계 중 마지막
    1) 적재  StockBuyCheckJob(평일 20:00) → trade_shape_train_daily
    2) 라벨  ShapeLabelJob(평일 21:40)    → net_edge_fwd 확정(5봉 엠바고)
    3) 학습  이 배치(토 02:00)            → 후보 학습 → 게이트 → 승격

자동 승격의 유일한 방어선은 게이트다
    승격 판정 로직은 stock_shared.ml.shape_train.evaluate_gate 에 전부 있다.
    이 파일은 DB 조회 / 아티팩트 저장 / 이력 기록만 하는 껍데기여야 한다 —
    판정 기준이 배치 코드에 섞이면 오프라인에서 같은 판정을 재현할 수 없다.

실패 시 동작
    학습/채점 중 예외는 Job.process 가 batch_log 에 FAIL 로 남기고 push 알림을 쏜다.
    **라이브 아티팩트는 승격 단계에 도달하기 전까지 절대 건드리지 않는다** — 중간에
    죽어도 라이브는 직전 모델 그대로다.

    선행조건(테이블·sklearn·아티팩트 쓰기권한)은 학습 전에 _preflight 가 확인하고
    하나라도 어긋나면 **FAIL 로 즉시 중단**한다. 데이터 부족(정상 대기)은 SUCCESS
    스킵이지만 선행조건 미비는 운영 설정 실수라 그날 바로 알려야 한다.

수동 실행
    POST /api/v1/jobs/once/SHAPE_TRAIN_JOB
    body:
      {"dry_run": true}        학습·채점·이력기록까지 하고 승격만 안 함(게이트 시험용)
      {"since": "2026-10-01"}  이 날짜 이후 학습셋만 사용
      {"holdout_days": 45}     holdout 구간을 넓혀 판정(기본 30)
"""
import json
import os
from datetime import datetime

from sqlalchemy import text

from app.batches.jobs.job import Job
from stock_shared.dao.tradeShapeModelHistDao import TradeShapeModelHistDao
from stock_shared.dao.tradeShapeTrainDailyDao import TradeShapeTrainDailyDao
from stock_shared.ml import shape_artifact, shape_model, shape_train
from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS
from stock_shared.models.tradeShapeModelHist import TradeShapeModelHist

# pre-flight 로 존재를 확인하는 테이블. sql/ 마이그레이션은 수동 적용이라
# "코드는 배포됐는데 DDL 만 안 돌린" 상태가 실제로 발생한다.
REQUIRED_TABLES = ('trade_shape_train_daily', 'trade_shape_model_hist')


class ShapeTrainJob(Job):
    def __init__(self):
        super().__init__()
        self.job_name = 'ShapeTrainJob'
        self.trainDaoImpl = TradeShapeTrainDailyDao()
        self.histDaoImpl = TradeShapeModelHistDao()

    def get_name(self):
        return self.job_name

    # ── pre-flight ───────────────────────────────────────────────────
    def _table_exists(self, table: str) -> bool:
        return bool(self.session.execute(
            text("SELECT COUNT(*) FROM information_schema.tables "
                 " WHERE table_schema = DATABASE() AND table_name = :t"),
            {"t": table},
        ).scalar())

    def _missing_hist_columns(self) -> list[str]:
        """ORM 모델에는 있는데 실제 테이블에 없는 컬럼. 있으면 INSERT 가 터진다."""
        have = {r[0] for r in self.session.execute(
            text("SELECT COLUMN_NAME FROM information_schema.columns "
                 " WHERE table_schema = DATABASE() "
                 "   AND table_name = 'trade_shape_model_hist'")).all()}
        need = {c.name for c in TradeShapeModelHist.__table__.columns}
        return sorted(need - have)

    def _preflight(self) -> list[str]:
        """학습을 시작하기 **전에** 선행조건을 확인한다. 반환: 문제 목록(빈 리스트=통과).

        왜 앞에서 막아야 하는가
            run_batch 는 '후보 저장 → 승격 → 이력 기록' 순이다. 이력 테이블이나 컬럼이
            없으면 **라이브 아티팩트를 교체한 뒤** 마지막 INSERT 에서 터진다 —
            배치 로그는 FAIL 인데 모델은 이미 바뀐, 가장 추적하기 어려운 상태가 된다.
            (2026-10-02 실제로 sql/20 만 적용되고 19 가 빠진 채 토요일 배치가 등록돼 있었다)

        왜 SUCCESS 스킵이 아니라 FAIL 인가
            데이터 부족은 정상적인 대기 상태라 SUCCESS 로 스킵한다. 반면 선행조건 미비는
            전부 **운영 설정 실수**다. 조용히 SUCCESS 로 끝내면 몇 주 뒤에야 알게 된다.
            FAIL 로 두면 batch_log 와 푸시 알림이 그날 바로 알려준다.
        """
        problems = []

        for table in REQUIRED_TABLES:
            if not self._table_exists(table):
                problems.append(f"{table} 테이블 없음(sql/ 마이그레이션 미적용)")

        # 테이블이 있어도 스키마가 어긋나면 같은 사고가 난다.
        if self._table_exists('trade_shape_model_hist'):
            missing = self._missing_hist_columns()
            if missing:
                problems.append("trade_shape_model_hist 컬럼 누락: " + ", ".join(missing))

        # 학습 배치에 sklearn 은 선택 의존성이 아니라 필수다(추론부와 다르다).
        try:
            import sklearn  # noqa: F401
        except Exception as e:  # noqa: BLE001
            problems.append(f"scikit-learn 사용 불가({type(e).__name__}: {e})")

        # 후보 저장·승격이 전부 파일 쓰기다. 학습을 다 돌린 뒤 쓰기에서 실패하면
        # 그 계산이 통째로 버려지므로 미리 실제로 써보고 지운다.
        try:
            os.makedirs(shape_artifact.CANDIDATES_DIR, exist_ok=True)
            probe = os.path.join(shape_artifact.CANDIDATES_DIR, f'.preflight_{os.getpid()}')
            with open(probe, 'w') as f:
                f.write('ok')
            os.remove(probe)
        except Exception as e:  # noqa: BLE001
            problems.append(f"후보 디렉터리 쓰기 불가({shape_artifact.CANDIDATES_DIR}): {e}")

        # 승격은 라이브 파일을 같은 디렉터리의 임시파일로 쓴 뒤 os.replace 한다.
        live_dir = os.path.dirname(shape_model.artifact_path())
        if not os.path.isdir(live_dir) or not os.access(live_dir, os.W_OK):
            problems.append(f"라이브 아티팩트 디렉터리 쓰기 불가({live_dir})")

        return problems

    def run_batch(self, **kwargs):
        dry_run = bool(kwargs.get('dry_run', False))
        since = kwargs.get('since')
        holdout_days = int(kwargs.get('holdout_days', shape_train.HOLDOUT_DAYS))
        run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        run_ymd = datetime.now().strftime('%Y-%m-%d')

        # ── 0) pre-flight — 학습·승격 전에 선행조건 확인 ────────────────────
        problems = self._preflight()
        if problems:
            desc = "선행조건 미비로 중단 — " + " / ".join(problems)
            print(f"[ShapeTrainJob] {desc}", flush=True)
            return {'status': 'FAIL', 'batch_cnt': 0, 'desc': desc[:255]}
        print("[ShapeTrainJob] pre-flight 통과 (테이블·sklearn·아티팩트 쓰기)", flush=True)

        # ── 1) 학습셋 로드 ──────────────────────────────────────────────────
        rows = self.trainDaoImpl.select_training_rows(self.session, since=since)
        summary = self.trainDaoImpl.count_summary(self.session)
        print(f"[ShapeTrainJob] 라벨확정 행 {len(rows)}건 로드 "
              f"(테이블 누적 {summary['total']}행 / 라벨 {summary['labeled']}행 / "
              f"{summary['min_dt']}~{summary['max_dt']})", flush=True)

        ds = shape_train.build_dataset(rows)
        print(f"[ShapeTrainJob] 학습가능 {len(ds.y)}행 "
              f"(피처결측 제외 {ds.dropped_incomplete} / 라벨결측 제외 {ds.dropped_unlabeled})",
              flush=True)

        # 데이터가 아예 없으면 학습 자체가 불가 — 이력도 남길 게 없으니 여기서 끝낸다.
        # (적재가 안 돌고 있다는 신호이므로 desc 에 그대로 드러낸다)
        if len(ds.y) == 0:
            desc = (f"학습가능 행 0건 — 학습 스킵. "
                    f"테이블 누적 {summary['total']}행 / 라벨 {summary['labeled']}행. "
                    f"적재(StockBuyCheckJob)와 라벨(ShapeLabelJob) 동작 여부를 확인하세요.")
            print(f"[ShapeTrainJob] {desc}", flush=True)
            return {'status': 'SUCCESS', 'batch_cnt': 0, 'desc': desc}

        # ── 2) 시간분할(엠바고 포함) ────────────────────────────────────────
        train_idx, holdout_idx, split = shape_train.time_split(
            ds, holdout_days=holdout_days)
        print(f"[ShapeTrainJob] 분할: train {len(train_idx)}행(~{split.get('train_end')}) / "
              f"holdout {len(holdout_idx)}행"
              f"({split.get('holdout_start')}~{split.get('holdout_end')}) / "
              f"엠바고 제외 {split.get('embargo_dropped')}행", flush=True)

        # 분할 결과가 비면 학습/채점을 시도할 의미가 없다(적재 초기). 게이트에
        # 넘기면 어차피 데이터부족으로 탈락하지만, 그 전에 model.fit 이 터진다.
        if len(train_idx) == 0 or len(holdout_idx) == 0:
            desc = (f"분할 불가 — train {len(train_idx)}행 / holdout {len(holdout_idx)}행. "
                    f"holdout {holdout_days}일 + 엠바고 {shape_train.EMBARGO_DAYS}일을 "
                    f"덮을 만큼 적재가 쌓이지 않았습니다"
                    f"(현재 {summary['min_dt']}~{summary['max_dt']}).")
            print(f"[ShapeTrainJob] {desc}", flush=True)
            return {'status': 'SUCCESS', 'batch_cnt': 0, 'desc': desc}

        # ── 3) 후보 학습 ────────────────────────────────────────────────────
        print(f"[ShapeTrainJob] 학습 시작 (params={shape_train.MODEL_PARAMS})", flush=True)
        candidate = shape_train.train_model(ds.X[train_idx], ds.y[train_idx])

        # ── 4) 같은 holdout 에서 후보/라이브 채점 ───────────────────────────
        train_m = shape_train.evaluate(candidate, ds, train_idx)
        cand_m = shape_train.evaluate(candidate, ds, holdout_idx)
        live_model = shape_artifact.load_live()
        live_m = shape_train.evaluate(live_model, ds, holdout_idx)

        print(f"[ShapeTrainJob] 후보  holdout: {cand_m.to_dict()}", flush=True)
        print(f"[ShapeTrainJob] 라이브 holdout: {live_m.to_dict()}", flush=True)
        print(f"[ShapeTrainJob] 학습 in-sample: {train_m.to_dict()}", flush=True)

        # ── 5) 게이트 ───────────────────────────────────────────────────────
        gate = shape_train.evaluate_gate(cand_m, live_m, train_m, split)
        print(f"[ShapeTrainJob] 게이트: {'승격' if gate.promote else '탈락'} — "
              f"{gate.reason_text}", flush=True)

        # ── 6) 후보는 승격 여부와 무관하게 항상 보관 ────────────────────────
        candidate_path = shape_artifact.save_candidate(candidate, run_id)

        # ── 7) 승격 ─────────────────────────────────────────────────────────
        backup_path = None
        promoted = False
        if gate.promote and dry_run:
            gate.reasons.append("dry_run=True → 승격 보류")
            print("[ShapeTrainJob] dry_run → 라이브 교체 생략", flush=True)
        elif gate.promote:
            res = shape_artifact.promote(candidate_path, run_id)
            backup_path = res['backup_path']
            promoted = True
            print(f"[ShapeTrainJob] 승격 완료 (백업: {backup_path})", flush=True)

        # ── 8) 이력 기록 ────────────────────────────────────────────────────
        self.histDaoImpl.insert_run(self.session, {
            'run_id': run_id,
            'run_ymd': run_ymd,
            'train_rows': train_m.n,
            'train_days': train_m.n_days,
            'train_pos_rate': shape_train.round_or_none(train_m.pos_rate),
            'holdout_rows': cand_m.n,
            'holdout_days': cand_m.n_days,
            'holdout_pos_rate': shape_train.round_or_none(cand_m.pos_rate),
            'holdout_start': split.get('holdout_start'),
            'holdout_end': split.get('holdout_end'),
            'train_end': split.get('train_end'),
            'dropped_incomplete': ds.dropped_incomplete,
            'dropped_unlabeled': ds.dropped_unlabeled,
            'cand_auc': shape_train.round_or_none(cand_m.auc),
            'cand_prec_at_k': shape_train.round_or_none(cand_m.prec_at_k),
            'cand_lift_at_k': shape_train.round_or_none(cand_m.lift_at_k),
            'live_auc': shape_train.round_or_none(live_m.auc),
            'live_prec_at_k': shape_train.round_or_none(live_m.prec_at_k),
            'live_lift_at_k': shape_train.round_or_none(live_m.lift_at_k),
            'promote_yn': 'Y' if promoted else 'N',
            'gate_reason': gate.reason_text[:1000],
            'candidate_path': candidate_path,
            'backup_path': backup_path,
            'sklearn_version': self._sklearn_version(),
            'model_params': json.dumps(shape_train.MODEL_PARAMS, ensure_ascii=False)[:500],
            'feature_cols': ','.join(SHAPE_FEATURE_COLUMNS),
        })
        self.session.commit()

        desc = (f"[{run_id}] {'승격' if promoted else '미승격'} — "
                f"후보 AUC {shape_train.round_or_none(cand_m.auc)} / "
                f"top{shape_train.PREC_AT_K} {shape_train.round_or_none(cand_m.prec_at_k)} "
                f"(라이브 AUC {shape_train.round_or_none(live_m.auc)} / "
                f"{shape_train.round_or_none(live_m.prec_at_k)}). "
                f"train {train_m.n}행 {train_m.n_days}일 / "
                f"holdout {cand_m.n}행 {cand_m.n_days}일. {gate.reason_text}")
        print(f"[ShapeTrainJob] {desc}", flush=True)
        return {'status': 'SUCCESS', 'batch_cnt': 1 if promoted else 0, 'desc': desc[:255]}

    @staticmethod
    def _sklearn_version() -> str | None:
        """학습 시 sklearn 버전. 아티팩트를 다른 버전에서 로드하면 경고/실패하므로
        나중에 원인 추적에 필요하다."""
        try:
            import sklearn
            return sklearn.__version__
        except Exception:  # noqa: BLE001
            return None
