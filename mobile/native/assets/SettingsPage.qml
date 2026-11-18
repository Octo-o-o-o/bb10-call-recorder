import bb.cascades 1.4

Page {
    id: settingsPage
    function t(key) { var l = recorderController.language; return recorderController.label(key); }

    titleBar: TitleBar { title: settingsPage.t("settings") }

    ScrollView {
        scrollViewProperties.scrollMode: ScrollMode.Vertical
        Container {
            leftPadding: 24
            rightPadding: 24
            topPadding: 16
            bottomPadding: 32

            CheckBox {
                text: settingsPage.t("auto_record")
                checked: recorderController.autoRecord
                enabled: recorderController.installed && !recorderController.busy
                onCheckedChanged: {
                    if (checked !== recorderController.autoRecord) {
                        recorderController.setAutoRecord(checked);
                    }
                }
            }

            CheckBox {
                text: settingsPage.t("include_number")
                checked: recorderController.includeNumber
                enabled: recorderController.installed && !recorderController.busy
                onCheckedChanged: {
                    if (checked !== recorderController.includeNumber) {
                        recorderController.setIncludeNumber(checked);
                    }
                }
            }

            DropDown {
                title: settingsPage.t("storage_title")
                enabled: recorderController.installed && !recorderController.busy
                options: [
                    Option {
                        text: settingsPage.t("storage_internal")
                        value: "internal"
                        selected: recorderController.storageLocation === "internal"
                    },
                    Option {
                        text: settingsPage.t("storage_sd")
                        value: "sdcard"
                        enabled: recorderController.sdAvailable
                        selected: recorderController.storageLocation === "sdcard"
                    }
                ]
                onSelectedOptionChanged: {
                    if (selectedOption && selectedOption.value !== recorderController.storageLocation) {
                        recorderController.setStorageLocation(selectedOption.value);
                    }
                }
            }

            DropDown {
                title: settingsPage.t("language")
                options: [
                    Option { text: "中文"; value: "zh"; selected: recorderController.language === "zh" },
                    Option { text: "English"; value: "en"; selected: recorderController.language === "en" }
                ]
                onSelectedOptionChanged: {
                    if (selectedOption) recorderController.language = selectedOption.value;
                }
            }

            Divider {}

            Button {
                visible: recorderController.volteInstalled
                enabled: !recorderController.busy
                horizontalAlignment: HorizontalAlignment.Fill
                text: recorderController.volteTapConfigured ? settingsPage.t("disable_volte_tap") : settingsPage.t("enable_volte_tap")
                onClicked: recorderController.setVolteTap(!recorderController.volteTapConfigured)
            }

            Button {
                visible: recorderController.installed
                enabled: !recorderController.busy
                horizontalAlignment: HorizontalAlignment.Fill
                text: settingsPage.t("uninstall")
                onClicked: recorderController.uninstallService()
            }
        }
    }
}
