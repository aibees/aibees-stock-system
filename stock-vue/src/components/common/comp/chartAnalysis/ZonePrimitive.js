// 가격 구간 박스(lightweight-charts series primitive) — from 시점부터 차트 오른쪽 끝까지 top~bottom 을 칠한다.
// 좌표는 그릴 때마다 시리즈/타임스케일에서 다시 구하므로 확대·이동에 따로 갱신할 것이 없다.
export class ZonePrimitive {
    constructor({ from, top, bottom, fill, stroke, label, textColor }) {
        this.opt = { from, top, bottom, fill, stroke, label, textColor }
        this._chart = null
        this._series = null
        const self = this
        this._view = {
            zOrder: () => 'bottom',
            renderer: () => ({ draw: (target) => self._draw(target) }),
        }
    }

    attached({ chart, series }) { this._chart = chart; this._series = series }
    detached() { this._chart = null; this._series = null }
    paneViews() { return [this._view] }

    _draw(target) {
        if (!this._chart || !this._series) return
        const { from, top, bottom, fill, stroke, label, textColor } = this.opt
        const y1 = this._series.priceToCoordinate(top)
        const y2 = this._series.priceToCoordinate(bottom)
        if (y1 == null || y2 == null) return
        const xFrom = this._chart.timeScale().timeToCoordinate(from)
        target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
            const x = Math.max(xFrom ?? 0, 0)
            const w = mediaSize.width - x
            if (w <= 0) return
            ctx.save()   // 글꼴·정렬 등 캔버스 상태를 다른 그리기에 남기지 않는다
            const y = Math.min(y1, y2)
            const h = Math.max(Math.abs(y2 - y1), 1)
            ctx.fillStyle = fill
            ctx.fillRect(x, y, w, h)
            if (stroke) {
                ctx.strokeStyle = stroke
                ctx.lineWidth = 1
                ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1)
            }
            if (label && h >= 12) {
                ctx.fillStyle = textColor || stroke || '#6B5B4E'
                ctx.font = "11px 'Pretendard', -apple-system, sans-serif"
                ctx.textBaseline = 'middle'
                // 왼쪽 끝은 봉·마커와 겹치기 쉬워 오른쪽 끝(가격축 옆)에 쓴다
                ctx.textAlign = 'right'
                ctx.fillText(label, x + w - 6, y + h / 2)
            }
            ctx.restore()
        })
    }
}
