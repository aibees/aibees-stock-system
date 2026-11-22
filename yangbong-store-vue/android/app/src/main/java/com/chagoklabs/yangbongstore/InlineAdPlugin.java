package com.chagoklabs.yangbongstore;

import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;
import android.widget.FrameLayout;

import androidx.annotation.NonNull;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.android.gms.ads.AdListener;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.AdSize;
import com.google.android.gms.ads.AdView;
import com.google.android.gms.ads.LoadAdError;

/**
 * 화면 안(스크롤되는 콘텐츠 사이)에 끼워 넣는 AdMob 배너 — 앱 안 플러그인(JS 이름 'InlineAd', 2026-11-22).
 * iOS 의 InlineAdPlugin.swift 와 같은 동작이다. 메서드·좌표 규칙은 그 파일 머리말을 따른다.
 *
 * 배너는 웹뷰 위에 얹은 칸(container) 안에 두고, 웹뷰 스크롤마다 자리를 옮긴다.
 * 칸은 헤더 아래~탭바 위만 보이게 잘라서 배너가 고정 헤더·탭바 위로 올라오지 않게 한다.
 * 칸 자체는 터치를 받지 않아(clickable=false) 배너 밖을 누르면 아래 웹뷰가 받는다.
 * 좌표는 CSS px → 기기 px 로 density 를 곱한다(viewport width=device-width 기준).
 */
@CapacitorPlugin(name = "InlineAd")
public class InlineAdPlugin extends Plugin {
    private FrameLayout container;
    private AdView banner;
    private boolean hiddenByWeb = false;

    // 웹 쪽 자리(CSS px)
    private double slotX, slotY, slotW, slotH, clipTop, clipBottom;

    @PluginMethod
    public void show(PluginCall call) {
        String adId = call.getString("adId");
        if (adId == null || adId.isEmpty()) {
            call.reject("adId 가 필요합니다.");
            return;
        }
        getActivity().runOnUiThread(() -> {
            WebView webView = getBridge().getWebView();
            if (webView == null || !(webView.getParent() instanceof ViewGroup)) {
                call.reject("웹뷰가 없습니다.");
                return;
            }
            removeAll();
            readGeometry(call);
            hiddenByWeb = false;

            ViewGroup parent = (ViewGroup) webView.getParent();
            container = new FrameLayout(getContext());
            container.setClipChildren(true);
            container.setClickable(false);
            container.setFocusable(false);
            parent.addView(container, new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

            banner = new AdView(getContext());
            banner.setAdSize(AdSize.BANNER);   // 320×50. 웹 자리 높이와 맞춘다(AdInlineBanner.vue)
            banner.setAdUnitId(adId);
            banner.setVisibility(View.INVISIBLE);
            banner.setAdListener(new AdListener() {
                @Override
                public void onAdLoaded() {
                    if (banner != null) banner.setVisibility(View.VISIBLE);
                    layout();
                    notifyListeners("loaded", new JSObject());
                }

                @Override
                public void onAdFailedToLoad(@NonNull LoadAdError error) {
                    if (banner != null) banner.setVisibility(View.INVISIBLE);
                    JSObject data = new JSObject();
                    data.put("message", error.getMessage());
                    notifyListeners("failed", data);
                }
            });
            container.addView(banner, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT));

            webView.setOnScrollChangeListener((v, x, y, oldX, oldY) -> layout());
            container.post(this::layout);
            banner.loadAd(new AdRequest.Builder().build());
            call.resolve();
        });
    }

    @PluginMethod
    public void update(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            readGeometry(call);
            layout();
            call.resolve();
        });
    }

    @PluginMethod
    public void setHidden(PluginCall call) {
        boolean hidden = Boolean.TRUE.equals(call.getBoolean("hidden", false));
        getActivity().runOnUiThread(() -> {
            hiddenByWeb = hidden;
            layout();
            call.resolve();
        });
    }

    @PluginMethod
    public void remove(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            removeAll();
            call.resolve();
        });
    }

    @Override
    protected void handleOnDestroy() {
        removeAll();
    }

    private void readGeometry(PluginCall call) {
        slotX = call.getDouble("x", slotX);
        slotY = call.getDouble("y", slotY);
        slotW = call.getDouble("width", slotW);
        slotH = call.getDouble("height", slotH);
        clipTop = call.getDouble("clipTop", clipTop);
        clipBottom = call.getDouble("clipBottom", clipBottom);
    }

    private void layout() {
        WebView webView = getBridge().getWebView();
        if (webView == null || container == null || banner == null) return;
        float d = getContext().getResources().getDisplayMetrics().density;

        // 자르는 칸: 헤더 아래 ~ 탭바 위 (웹뷰와 같은 자리에서 시작)
        int top = (int) Math.round(clipTop * d);
        int height = Math.max(0, webView.getHeight() - top - (int) Math.round(clipBottom * d));
        container.setX(webView.getX());
        container.setY(webView.getY() + top);
        ViewGroup.LayoutParams lp = container.getLayoutParams();
        if (lp.width != webView.getWidth() || lp.height != height) {
            lp.width = webView.getWidth();
            lp.height = height;
            container.setLayoutParams(lp);
        }
        container.setVisibility(hiddenByWeb ? View.GONE : View.VISIBLE);

        // 배너: 자리의 가운데(문서 좌표 − 스크롤 − 칸 위치)
        int bw = AdSize.BANNER.getWidthInPixels(getContext());
        int bh = AdSize.BANNER.getHeightInPixels(getContext());
        float cx = (float) ((slotX + slotW / 2) * d) - webView.getScrollX();
        float cy = (float) ((slotY + slotH / 2) * d) - webView.getScrollY() - top;
        banner.setX(cx - bw / 2f);
        banner.setY(cy - bh / 2f);
    }

    private void removeAll() {
        WebView webView = getBridge() != null ? getBridge().getWebView() : null;
        if (webView != null) webView.setOnScrollChangeListener(null);
        if (banner != null) {
            banner.destroy();
            banner = null;
        }
        if (container != null) {
            if (container.getParent() instanceof ViewGroup) ((ViewGroup) container.getParent()).removeView(container);
            container = null;
        }
    }
}
