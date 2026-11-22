import Foundation
import AuthenticationServices
import CryptoKit
import Capacitor

/// Sign in with Apple — 앱 안 플러그인(JS 이름 'AppleSignIn').
/// 공개 플러그인(@capacitor-community/apple-sign-in 7.x)은 capacitor-swift-pm 을 7.x 로 묶어 Capacitor 8 과 함께 못 쓴다.
///
/// authorize({ nonce }) → { identityToken, authorizationCode, user, email, givenName, familyName }
///   nonce 는 원문을 받아 sha256 hex 로 바꿔 Apple 요청에 넣는다(서버가 같은 방식으로 비교).
@objc(AppleSignInPlugin)
public class AppleSignInPlugin: CAPPlugin, CAPBridgedPlugin, ASAuthorizationControllerDelegate,
                                ASAuthorizationControllerPresentationContextProviding {
    public let identifier = "AppleSignInPlugin"
    public let jsName = "AppleSignIn"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "authorize", returnType: CAPPluginReturnPromise)
    ]

    private var pendingCall: CAPPluginCall?

    @objc func authorize(_ call: CAPPluginCall) {
        guard let nonce = call.getString("nonce"), !nonce.isEmpty else {
            call.reject("nonce 가 필요합니다.")
            return
        }
        if pendingCall != nil {
            call.reject("이미 Apple 로그인을 진행 중입니다.")
            return
        }
        pendingCall = call

        let request = ASAuthorizationAppleIDProvider().createRequest()
        request.requestedScopes = [.fullName, .email]
        request.nonce = SHA256.hash(data: Data(nonce.utf8)).map { String(format: "%02x", $0) }.joined()

        DispatchQueue.main.async {
            let controller = ASAuthorizationController(authorizationRequests: [request])
            controller.delegate = self
            controller.presentationContextProvider = self
            controller.performRequests()
        }
    }

    public func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        return bridge?.webView?.window ?? ASPresentationAnchor()
    }

    public func authorizationController(controller: ASAuthorizationController,
                                        didCompleteWithAuthorization authorization: ASAuthorization) {
        guard let call = pendingCall else { return }
        pendingCall = nil
        guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
              let tokenData = credential.identityToken, let token = String(data: tokenData, encoding: .utf8),
              let codeData = credential.authorizationCode, let code = String(data: codeData, encoding: .utf8) else {
            call.reject("Apple 인증 정보를 받지 못했습니다.")
            return
        }
        call.resolve([
            "identityToken": token,
            "authorizationCode": code,
            "user": credential.user,
            "email": credential.email ?? NSNull(),
            "givenName": credential.fullName?.givenName ?? NSNull(),
            "familyName": credential.fullName?.familyName ?? NSNull(),
        ])
    }

    public func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
        guard let call = pendingCall else { return }
        pendingCall = nil
        if let err = error as? ASAuthorizationError, err.code == .canceled {
            call.reject("canceled", "CANCELED")
        } else {
            call.reject(error.localizedDescription, "FAILED", error)
        }
    }
}

/// 앱 안 플러그인을 등록하는 브리지 화면(SceneDelegate 가 루트로 쓴다).
class MainViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(AppleSignInPlugin())
        bridge?.registerPluginInstance(InlineAdPlugin())   // 홈 '공지사항 위' AdMob 배너 — InlineAdPlugin.swift
    }
}
