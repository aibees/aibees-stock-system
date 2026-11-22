package com.chagoklabs.yangbongstore;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(InlineAdPlugin.class);   // 홈 '공지사항 위' AdMob 배너 — InlineAdPlugin.java
        super.onCreate(savedInstanceState);
    }
}
