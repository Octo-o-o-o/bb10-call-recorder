import bb.cascades 1.4

NavigationPane {
    id: nav
    function t(key) { var l = recorderController.language; return recorderController.label(key); }
    onPopTransitionEnded: { page.destroy(); }

    Page {
        titleBar: TitleBar {
            title: nav.t("app_title")
            acceptAction: ActionItem {
                title: "OctoLab"
                enabled: !recorderController.busy
                onTriggered: {
                    var page = supportDef.createObject();
                    page.appNavigation = nav;
                    nav.push(page);
                }
            }
        }
        actions: [
            ActionItem {
                title: nav.t("recordings")
                ActionBar.placement: ActionBarPlacement.OnBar
                onTriggered: nav.push(recordingsDef.createObject())
            },
            ActionItem {
                title: nav.t("settings")
                ActionBar.placement: ActionBarPlacement.OnBar
                onTriggered: nav.push(settingsDef.createObject())
            },
            ActionItem {
                title: nav.t("refresh")
                enabled: !recorderController.busy
                shortcuts: [ Shortcut { key: "R" } ]
                onTriggered: recorderController.refresh()
            }
        ]

        ScrollView {
            horizontalAlignment: HorizontalAlignment.Fill
            verticalAlignment: VerticalAlignment.Fill
            scrollViewProperties.scrollMode: ScrollMode.Vertical
            Container {
                leftPadding: 24
                rightPadding: 24
                topPadding: 20
                bottomPadding: 32

                Label {
                    text: nav.t("tagline")
                    multiline: true
                    textStyle.fontSize: FontSize.Small
                    textFormat: TextFormat.Plain
                }
                Divider {}

                Label {
                    text: recorderController.statusTitle
                    multiline: true
                    textStyle.fontSize: FontSize.XLarge
                    textStyle.fontWeight: FontWeight.W500
                    textFormat: TextFormat.Plain
                }
                Label {
                    text: recorderController.statusDetail
                    multiline: true
                    textStyle.fontSize: FontSize.Small
                    textFormat: TextFormat.Plain
                }
                Label {
                    text: recorderController.engineText
                    multiline: true
                    textStyle.fontSize: FontSize.Small
                    textFormat: TextFormat.Plain
                }

                ActivityIndicator {
                    visible: recorderController.busy
                    running: visible
                    preferredWidth: 64
                    preferredHeight: 64
                    horizontalAlignment: HorizontalAlignment.Center
                }

                Container {
                    visible: recorderController.installed && !recorderController.consentAcknowledged
                    topPadding: 12
                    Label {
                        text: nav.t("consent_title")
                        textStyle.fontWeight: FontWeight.W500
                        textFormat: TextFormat.Plain
                    }
                    Label {
                        text: nav.t("consent_body")
                        multiline: true
                        textStyle.fontSize: FontSize.Small
                        textFormat: TextFormat.Plain
                    }
                    Button {
                        text: nav.t("consent_accept")
                        horizontalAlignment: HorizontalAlignment.Fill
                        enabled: !recorderController.busy
                        onClicked: recorderController.acknowledgeConsent()
                    }
                }

                Button {
                    text: nav.t("install_service")
                    visible: !recorderController.installed
                    enabled: !recorderController.busy
                    horizontalAlignment: HorizontalAlignment.Fill
                    onClicked: recorderController.installService()
                }

                Button {
                    text: recorderController.recordingActive ? nav.t("stop_manual") : nav.t("start_manual")
                    visible: recorderController.installed && recorderController.consentAcknowledged
                    enabled: !recorderController.busy && (recorderController.recordingActive || recorderController.callEligible)
                    horizontalAlignment: HorizontalAlignment.Fill
                    onClicked: {
                        if (recorderController.recordingActive) recorderController.stopManual();
                        else recorderController.startManual();
                    }
                }

                Button {
                    text: nav.t("recordings") + " (" + recorderController.recordings.length + ")"
                    horizontalAlignment: HorizontalAlignment.Fill
                    onClicked: nav.push(recordingsDef.createObject())
                }

                Label {
                    text: recorderController.folderText
                    multiline: true
                    textStyle.fontSize: FontSize.XSmall
                    textFormat: TextFormat.Plain
                }
                Label {
                    text: recorderController.notice
                    visible: text.length > 0
                    multiline: true
                    textStyle.fontSize: FontSize.Small
                    textFormat: TextFormat.Plain
                }
            }
        }
    }

    attachedObjects: [
        ComponentDefinition { id: supportDef; source: "Support.qml" },
        ComponentDefinition { id: recordingsDef; source: "RecordingsPage.qml" },
        ComponentDefinition { id: settingsDef; source: "SettingsPage.qml" }
    ]
}
