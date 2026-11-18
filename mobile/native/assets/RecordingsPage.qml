import bb.cascades 1.4
import bb.multimedia 1.4

Page {
    id: recPage
    property string activePlayId: ""
    function t(key) { var l = recorderController.language; return recorderController.label(key); }
    function syncList() {
        listModel.clear();
        listModel.append(recorderController.recordings);
    }

    titleBar: TitleBar {
        title: recPage.t("recordings")
        acceptAction: ActionItem {
            title: recPage.t("refresh")
            enabled: !recorderController.busy
            onTriggered: recorderController.refresh()
        }
    }
    onCreationCompleted: {
        recPage.syncList();
        recorderController.stateChanged.connect(recPage.syncList);
    }

    Container {
        leftPadding: 20
        rightPadding: 20
        topPadding: 12

        Label {
            text: recPage.t("empty_list")
            visible: recorderController.recordings.length === 0
            multiline: true
            textFormat: TextFormat.Plain
        }

        ListView {
            dataModel: ArrayDataModel { id: listModel }
            listItemComponents: [
                ListItemComponent {
                    type: ""
                    Container {
                        topPadding: 12
                        bottomPadding: 12
                        Label {
                            text: ListItemData.filename
                            textStyle.fontWeight: FontWeight.W500
                            textFormat: TextFormat.Plain
                        }
                        Label {
                            text: ListItemData.peer + "  ·  " + ListItemData.duration_sec + "s  ·  " + ListItemData.engine
                            textStyle.fontSize: FontSize.Small
                            textFormat: TextFormat.Plain
                        }
                        Container {
                            layout: StackLayout { orientation: LayoutOrientation.LeftToRight }
                            Button {
                                text: ListItem.view.contextPage.t("play")
                                onClicked: ListItem.view.contextPage.playFile(ListItemData.id, ListItemData.path)
                            }
                            Button {
                                text: ListItem.view.contextPage.t("stop_play")
                                onClicked: ListItem.view.contextPage.stopPlay()
                            }
                            Button {
                                text: ListItem.view.contextPage.t("delete")
                                onClicked: ListItem.view.contextPage.removeItem(ListItemData.id)
                            }
                        }
                        Divider {}
                    }
                }
            ]
            property variant contextPage: recPage
        }
    }

    function playFile(id, path) {
        player.stop();
        player.sourceUrl = "file://" + path;
        activePlayId = id;
        player.play();
    }

    function stopPlay() {
        player.stop();
        activePlayId = "";
    }

    function removeItem(id) {
        if (activePlayId === id) stopPlay();
        recorderController.deleteRecording(id);
    }

    attachedObjects: [
        MediaPlayer { id: player }
    ]
}
