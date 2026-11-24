import Foundation
import UIKit
import Capacitor
import GoogleMobileAds

/// 화면 안(스크롤되는 콘텐츠 사이)에 끼워 넣는 AdMob 배너 — 앱 안 플러그인(JS 이름 'InlineAd', 2026-11-22).
///
/// @capacitor-community/admob 의 배너는 화면 위/아래 고정만 돼서 홈 '공지사항 위' 같은 자리에 못 넣는다.
/// 그래서 배너를 웹뷰 위에 얹되, 웹 화면의 자리(placeholder div)를 따라 스크롤마다 옮긴다.
///
///   show({ adId, x, y, width, height, clipTop, clipBottom })
///       x, y        : 자리의 문서 좌표(CSS px, getBoundingClientRect + scrollX/Y). 배너는 그 칸 가운데에 놓인다.
///       width       : 칸 너비. 배너는 이 너비를 꽉 채우는 적응형(anchored adaptive)으로 만든다(2026-11-23).
///                     resolve 값 { width, height } 로 SDK 가 정한 크기를 돌려준다 — 웹이 칸 높이를 맞춘다.
///       clipTop     : 화면 위쪽에서 가려야 하는 높이(고정 헤더 아래 끝, CSS px). 배너가 헤더 위로 올라오지 않게 자른다.
///       clipBottom  : 화면 아래쪽에서 가려야 하는 높이(하단 탭바). 같은 이유.
///   update({ x, y, width, height, clipTop, clipBottom }) : 자리가 바뀌었을 때(레이아웃 변화) 다시 맞춘다.
///   setHidden({ hidden }) : 웹 팝업이 위에 뜰 때 잠깐 숨긴다(네이티브 배너는 웹 요소보다 늘 위에 그려진다).
///   remove()    : 화면을 떠날 때.
/// 이벤트: 'loaded' / 'failed' {message}
///
/// SDK 초기화(MobileAds.start, 동의)는 @capacitor-community/admob 의 initialize 가 이미 한다(useAdMob.initAdMob).
/// 스크롤은 웹뷰 scrollView 의 contentOffset 을 KVO 로 보고 네이티브에서 바로 옮긴다 — JS 를 거치지 않아 끊기지 않는다.
@objc(InlineAdPlugin)
public class InlineAdPlugin: CAPPlugin, CAPBridgedPlugin, BannerViewDelegate {
    public let identifier = "InlineAdPlugin"
    public let jsName = "InlineAd"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "show", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "update", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setHidden", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "remove", returnType: CAPPluginReturnPromise)
    ]

    /// 배너를 잘라 보여 주는 칸(웹뷰 위, 헤더~탭바 사이). 배너 밖은 터치를 웹뷰로 흘려보낸다.
    private var container: PassThroughView?
    private var banner: BannerView?
    private var offsetObservation: NSKeyValueObservation?

    // 웹 쪽 자리(CSS px)
    private var slot = CGRect.zero
    private var clipTop: CGFloat = 0
    private var clipBottom: CGFloat = 0
    private var hiddenByWeb = false

    @objc func show(_ call: CAPPluginCall) {
        guard let adId = call.getString("adId"), !adId.isEmpty else {
            call.reject("adId 가 필요합니다.")
            return
        }
        DispatchQueue.main.async {
            guard let webView = self.bridge?.webView else {
                call.reject("웹뷰가 없습니다.")
                return
            }
            self.removeAll()
            self.readGeometry(call)
            self.hiddenByWeb = false

            let box = PassThroughView(frame: .zero)
            box.clipsToBounds = true
            box.backgroundColor = .clear
            webView.addSubview(box)
            self.container = box

            // 칸 너비를 꽉 채우는 적응형 배너. 높이는 너비에 따라 SDK 가 정한다(보통 50~60pt).
            let width = self.slot.width > 0 ? self.slot.width : webView.bounds.width
            let adSize = currentOrientationAnchoredAdaptiveBanner(width: width)
            let banner = BannerView(adSize: adSize)
            banner.adUnitID = adId
            banner.rootViewController = self.bridge?.viewController
            banner.delegate = self
            banner.isHidden = true   // 광고가 오기 전에는 빈 칸을 그리지 않는다
            box.addSubview(banner)
            self.banner = banner

            self.offsetObservation = webView.scrollView.observe(\.contentOffset, options: [.new]) { [weak self] _, _ in
                self?.layout()
            }
            self.layout()
            banner.load(Request())
            call.resolve(["width": adSize.size.width, "height": adSize.size.height])
        }
    }

    @objc func update(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.readGeometry(call)
            self.layout()
            call.resolve()
        }
    }

    @objc func setHidden(_ call: CAPPluginCall) {
        let hidden = call.getBool("hidden") ?? false
        DispatchQueue.main.async {
            self.hiddenByWeb = hidden
            self.layout()
            call.resolve()
        }
    }

    @objc func remove(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.removeAll()
            call.resolve()
        }
    }

    private func readGeometry(_ call: CAPPluginCall) {
        let num = { (key: String, fallback: CGFloat) -> CGFloat in
            if let v = call.getDouble(key) { return CGFloat(v) }
            return fallback
        }
        slot = CGRect(x: num("x", slot.origin.x), y: num("y", slot.origin.y),
                      width: num("width", slot.width), height: num("height", slot.height))
        clipTop = num("clipTop", clipTop)
        clipBottom = num("clipBottom", clipBottom)
    }

    /// 웹 자리 → 화면 좌표. 확대(zoomScale)·스크롤(contentOffset)을 반영한다.
    private func layout() {
        guard let webView = bridge?.webView, let box = container, let banner = banner else { return }
        let sv = webView.scrollView
        let zoom = sv.zoomScale
        let bounds = webView.bounds

        // 자르는 칸: 헤더 아래 ~ 탭바 위
        let top = clipTop * zoom
        let bottom = max(top, bounds.height - clipBottom * zoom)
        box.frame = CGRect(x: 0, y: top, width: bounds.width, height: bottom - top)
        box.isHidden = hiddenByWeb

        // 배너: 자리의 가운데에 놓는다(문서 좌표 × 확대 − 스크롤 − 칸 위치).
        // 사용자가 화면을 확대해도 배너 자체 크기는 그대로다(광고 소재를 늘려 그리면 약관 위반).
        let size = banner.adSize.size
        let centerX = (slot.midX * zoom) - sv.contentOffset.x
        let centerY = (slot.midY * zoom) - sv.contentOffset.y - top
        banner.bounds = CGRect(origin: .zero, size: size)
        banner.center = CGPoint(x: centerX, y: centerY)
    }

    private func removeAll() {
        offsetObservation?.invalidate()
        offsetObservation = nil
        banner?.delegate = nil
        banner?.removeFromSuperview()
        banner = nil
        container?.removeFromSuperview()
        container = nil
    }

    // MARK: BannerViewDelegate

    public func bannerViewDidReceiveAd(_ bannerView: BannerView) {
        bannerView.isHidden = false
        layout()
        notifyListeners("loaded", data: [:])
    }

    public func bannerView(_ bannerView: BannerView, didFailToReceiveAdWithError error: Error) {
        NSLog("[InlineAd] 배너 로드 실패: \(error.localizedDescription)")
        bannerView.isHidden = true
        notifyListeners("failed", data: ["message": error.localizedDescription])
    }
}

/// 자기 자신은 터치를 받지 않고, 안에 있는 배너만 받는다 — 배너 밖을 누르면 그대로 웹뷰가 받는다.
final class PassThroughView: UIView {
    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        let hit = super.hitTest(point, with: event)
        return hit === self ? nil : hit
    }
}
