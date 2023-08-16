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

import QtCore
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import djpdf

Page {
    FileDialog {
        id: openDialog
        title: N_("Open")
        nameFilters: [
            `${N_("Images")} (${pagesModel.imageFileExtensions.map(s => `*.${s}`).join(" ")})`,
            `${N_("All files")} (*)`,
        ]
        fileMode: FileDialog.OpenFiles
        currentFolder: StandardPaths.writableLocation(StandardPaths.HomeLocation)
        onAccepted: pagesModel.extend(selectedFiles)
    }

    FileDialog {
        id: saveDialog
        title: N_("Save")
        nameFilters: [ `${N_("PDF")} (*.${pagesModel.pdfFileExtension})` ]
        fileMode: FileDialog.SaveFile
        currentFolder: StandardPaths.writableLocation(StandardPaths.HomeLocation)
        onAccepted: pagesModel.save(selectedFile)
    }

    Connections {
        target: pagesModel
        function onSavingError(message) {
            errorDialog.text = message
            errorDialog.open()
        }
    }

    Popup {
        property string text

        id: errorDialog
        parent: stack
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        modal: true
        focus: true
        width: parent.width * 0.8
        height: Math.min(parent.height * 0.8, implicitHeight)
        closePolicy: Popup.CloseOnEscape
        onClosed: text = ""
        ColumnLayout {
            anchors.fill: parent
            Label {
                text: N_("Failed to create PDF")
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                TextArea {
                    text: errorDialog.text
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    readOnly: true
                }
            }
            Button {
                text: N_("Close")
                Layout.alignment: Qt.AlignRight
                onClicked: errorDialog.close()
            }
        }
    }

    Popup {
        parent: stack
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        modal: true
        focus: true
        visible: pagesModel.saving
        closePolicy: Popup.NoAutoClose
        ColumnLayout {
            anchors.fill: parent
            Label {
                text: N_("Saving...")
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                Layout.fillWidth: true
            }
            ProgressBar {
                Layout.fillWidth: true
                Layout.fillHeight: true
                value: pagesModel.savingProgress
                topPadding: 15
                bottomPadding: 15
            }
            Button {
                text: N_("Cancel")
                Layout.alignment: Qt.AlignRight
                onClicked: pagesModel.cancelSaving()
                enabled: pagesModel.savingCancelable
            }
        }
    }

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            ToolButton {
                text: "+"
                onClicked: openDialog.open()
            }
            Item {
                Layout.fillWidth: true
            }
            ToolButton {
                text: N_("Create")
                enabled: pagesModel.count > 0
                onClicked: saveDialog.open()
            }
        }
    }

    ScrollView {
        anchors.fill: parent
        background: Rectangle {
            color: paletteActive.base
        }

        GridView {
            property string dragKey: "9e8acb18cd58e838"

            id: pagesView
            focus: true
            activeFocusOnTab: true
            model: pagesModel

            Keys.onSpacePressed: {
                event.accepted = true
                stack.push("detail.qml", {p: pagesView.currentItem.p,
                                          modelIndex: pagesView.currentItem.modelIndex})
            }

            cellWidth: 100
            cellHeight: 150
            delegate: MouseArea {
                id: pageDelegate

                property int modelIndex: index
                property DjpdfPage p: model.modelData
                property bool active: GridView.isCurrentItem && pagesView.activeFocus

                onClicked: stack.push("detail.qml", {p: p, modelIndex: modelIndex})

                onPressed: {
                    pagesView.forceActiveFocus(Qt.MouseFocusReason)
                    pagesView.currentIndex = modelIndex
                }

                width: pagesView.cellWidth
                height: pagesView.cellHeight
                drag.target: pageItem
                Item {
                    id: pageItem
                    width: pageDelegate.width
                    height: pageDelegate.height
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: parent.verticalCenter

                    Drag.active: pageDelegate.drag.active
                    Drag.source: pageDelegate
                    Drag.hotSpot.x: width/2
                    Drag.hotSpot.y: height/2
                    Drag.keys: [ pagesView.dragKey ]

                    states: [
                        State {
                            when: pageItem.Drag.active
                            ParentChange {
                                target: pageItem
                                parent: pagesView
                            }

                            AnchorChanges {
                                target: pageItem
                                anchors.horizontalCenter: undefined
                                anchors.verticalCenter: undefined
                            }
                        }
                    ]

                    Image {
                        id: image
                        anchors {
                            left: parent.left
                            right: parent.right
                            top: parent.top
                            bottom: title.top
                            margins: 6
                        }
                        asynchronous: true
                        source: "image://thumbnails/" + model.modelData.url
                        fillMode: Image.PreserveAspectFit
                        verticalAlignment: Image.AlignBottom
                        z: 1
                    }
                    Rectangle {
                        anchors {
                            horizontalCenter: image.horizontalCenter
                            bottom: image.bottom
                            bottomMargin: (image.paintedHeight-height)/2
                        }
                        width: image.paintedWidth + 4
                        height: image.paintedHeight + 4
                        visible: image.status === Image.Ready
                        color: paletteActive.text
                    }
                    BusyIndicator {
                        anchors.centerIn: image
                        running: image.status !== Image.Ready
                    }

                    Label {
                        id: title
                        anchors { fill: parent; topMargin: 100 }
                        color: pageDelegate.active ? paletteActive.highlightedText : paletteActive.text
                        text: pageDelegate.p.displayName
                        wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                        leftPadding: 5
                        rightPadding: 5
                        bottomPadding: 3
                        z: 1
                    }
                    Rectangle {
                        anchors { horizontalCenter: title.horizontalCenter; top: title.top }
                        color: paletteActive.highlight
                        visible: pageDelegate.active
                        height: title.contentHeight + 3
                        width: title.contentWidth + 6
                    }
                }

                DropArea {
                    anchors { fill: parent; margins: 5 }
                    keys: [ pagesView.dragKey ]
                    onEntered: pagesModel.move(drag.source.modelIndex, pageDelegate.modelIndex)
                }
            }
        }
    }
}
