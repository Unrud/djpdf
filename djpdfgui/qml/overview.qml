/*
 *    This file is part of djpdf.
 *
 *    djpdf is free software: you can redistribute it and/or modify
 *    it under the terms of the GNU General Public License as published by
 *    the Free Software Foundation, either version 3 of the License, or
 *    (at your option) any later version.
 *
 *    Foobar is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *    GNU General Public License for more details.
 *
 *    You should have received a copy of the GNU General Public License
 *    along with djpdf.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Copyright 2018 Unrud <unrud@outlook.com>
 */

import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3
import QtQuick.Dialogs 1.2
import QtGraphicalEffects 1.0
import djpdf 1.0

Page {
    FileDialog {
        id: openDialog
        title: "Open"
        nameFilters: [
            "Images (" + platformIntegration.imageFileExtensions.map(function(s) {return "*." + s}).join(" ") + ")",
            "All files (*)"
        ]
        folder: shortcuts.home
        selectMultiple: true
        onAccepted: pagesModel.extend(openDialog.fileUrls)
    }

    FileDialog {
        id: saveDialog
        title: "Save"
        defaultSuffix: platformIntegration.pdfFileExtension
        nameFilters: [ "PDF (*." + platformIntegration.pdfFileExtension + ")" ]
        folder: shortcuts.home
        selectExisting: false
        onAccepted: pagesModel.save(saveDialog.fileUrl)
    }

    Connections {
        target: platformIntegration
        function onOpened(urls) {
            pagesModel.extend(urls);
        }
        function onSaved(url) {
            pagesModel.save(url);
        }
    }

    MessageDialog {
        id: errorDialog
        title: "Error"
        text: "Failed to create PDF"
    }

    Connections {
        target: pagesModel
        function onSavingError() {
            errorDialog.open()
        }
    }

    Popup {
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        modal: true
        visible: pagesModel.saving
        closePolicy: Popup.NoAutoClose
        ColumnLayout {
            anchors.fill: parent
            Label {
                text: "Saving..."
            }
            ProgressBar {
                Layout.fillWidth: true
                value: pagesModel.savingProgress
            }
            Item {
                Layout.fillHeight: true
            }
        }
    }

    header: ToolBar {
        RowLayout {

            anchors.fill: parent
            ToolButton {
                text: "+"
                onClicked: {
                    if (platformIntegration.enabled)
                        platformIntegration.openOpenDialog();
                    else
                        openDialog.open();
                }
            }
            Item {
                Layout.fillWidth: true
            }
            ToolButton {
                text: "Create"
                enabled: pagesModel.count > 0
                onClicked: {
                    if (platformIntegration.enabled)
                        platformIntegration.openSaveDialog();
                    else
                        saveDialog.open();
                }
            }
        }
    }

    ScrollView {
        anchors.fill: parent
        background: Rectangle {
            color: paletteActive.base
        }

        GridView {
            id: listView

            focus: true
            model: pagesModel
            highlight: Rectangle {
                color: listView.activeFocus ? paletteActive.highlight : "transparent"
            }
            Keys.onSpacePressed: {
                event.accepted = true
                stack.push("detail.qml", {p: listView.currentItem.p,
                                          modelIndex: listView.currentItem.visualIndex})
            }

            delegate: MouseArea {
                id: delegateRoot

                property int visualIndex: index
                property DjpdfPage p: model.modelData

                onReleased: {
                    if (!drag.active)
                        stack.push("detail.qml", {p: model.modelData,
                                                  modelIndex: index})
                }

                width: 100
                height: 100
                drag.target: icon
                Item {
                    id: icon
                    //color: "transparent"
                    //highlighted: GridView.isCurrentItem
                    //onClicked: listView.currentIndex = index
                    width: 100
                    height: 100
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: parent.verticalCenter

                    Drag.active: delegateRoot.drag.active
                    Drag.source: delegateRoot
                    Drag.hotSpot.x: width/2
                    Drag.hotSpot.y: height/2
                    Drag.keys: ["73439a2262016118"]

                    states: [
                        State {
                            when: icon.Drag.active
                            ParentChange {
                                target: icon
                                parent: listView
                            }

                            AnchorChanges {
                                target: icon;
                                anchors.horizontalCenter: undefined;
                                anchors.verticalCenter: undefined
                            }
                        }
                    ]

                    Image {
                        id: image
                        asynchronous: true
                        source: "image://thumbnails/" + model.modelData.url
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectFit
                        anchors.margins: 6
                        z: 1
                    }
                    Rectangle {
                        id: borderx
                        color: paletteActive.text
                        anchors.centerIn: image
                        width: image.paintedWidth + 2
                        height: image.paintedHeight + 2
                        visible: image.status === Image.Ready
                    }

                    DropShadow {
                        anchors.fill: source
                        cached: true
                        horizontalOffset: 0
                        verticalOffset: 1
                        radius: 8
                        samples: 16
                        color: paletteActive.text
                        smooth: true
                        source: borderx
                    }

                    BusyIndicator {
                        running: image.status !== Image.Ready
                        anchors.centerIn: parent
                    }
                }

                DropArea {
                    anchors { fill: parent; margins: 15 }
                    keys: ["73439a2262016118"]
                    onEntered: {
                        pagesModel.swap(drag.source.visualIndex, delegateRoot.visualIndex)
                    }
                }
            }
        }
    }
}
