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
import djpdf 1.0

Page {
    id: sv
    property int modelIndex: 0
    property DjpdfPage p: DjpdfPage{}
    property real leftColumnWidth: Math.max(
        l1.implicitWidth, l2.implicitWidth, l3.implicitWidth, l4.implicitWidth,
        l5.implicitWidth, l6.implicitWidth, l7.implicitWidth, l8.implicitWidth,
        l9.implicitWidth, l10.implicitWidth)

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            ToolButton {
                text: "‹"
                onClicked: stack.pop()
            }
            ToolButton {
                text: "Remove"
                highlighted: true
                onClicked: {
                    stack.pop()
                    pagesModel.remove(sv.modelIndex)
                }
            }
            Label {
                text: sv.p.displayName
                font.bold: true
                elide: Text.ElideMiddle
                textFormat: Text.PlainText
                horizontalAlignment: Text.AlignHCenter
                leftPadding: 5
                rightPadding: 5 + x
                Layout.fillWidth: true
            }
        }
    }

    ColorDialog {
        property var fn: null
        id: colorDialog
        title: "Please choose a color"
        modality: Qt.WindowModal
        onAccepted: fn()
    }

    ScrollView {
        id: scrollView
        anchors.fill: parent
        padding: 5
        ColumnLayout {
            width: scrollView.availableWidth

            Pane {
                Layout.fillWidth: true
                ColumnLayout {
                    anchors.fill: parent
                    RowLayout {
                        Label {
                            id: l1
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "DPI:"
                        }
                        TextField {
                            Layout.fillWidth: true
                            selectByMouse: true
                            placeholderText: "auto"
                            text: sv.p.dpi !== 0 ? sv.p.dpi : ""
                            validator: RegExpValidator { regExp: /[0-9]*/ }
                            onEditingFinished: {
                                if (text === "") {
                                    sv.p.dpi = 0
                                } else {
                                    sv.p.dpi = parseInt(text)
                                }
                            }
                        }
                    }
                    RowLayout {
                        Label {
                            id: l2
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "Background color:"
                        }
                        Button {
                            Layout.fillWidth: true
                            onClicked: {
                                colorDialog.fn = function() {
                                    sv.p.bgColor = colorDialog.color
                                }
                                colorDialog.color = sv.p.bgColor
                                colorDialog.open()
                            }
                            Rectangle {
                                color: parent.enabled ? paletteActive.buttonText : paletteDisabled.buttonText
                                anchors.fill: parent
                                anchors.margins: 5
                                Rectangle {
                                    color: sv.p.bgColor
                                    anchors.fill: parent
                                    anchors.margins: 1
                                }
                            }
                        }
                    }
                }
            }

            GroupBox {
                Layout.fillWidth: true
                label: RowLayout {
                    width: parent.width
                    Label {
                        text: "Background"
                        font.bold: true
                    }
                    Switch {
                        Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                        checked: sv.p.bg
                        onToggled: sv.p.bg = checked && true
                    }
                }

                ColumnLayout {
                    enabled: sv.p.bg
                    anchors.fill: parent
                    RowLayout {
                        Label {
                            id: l3
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "Resize:"
                        }
                        SpinBox {
                            Layout.fillWidth: true
                            editable: true
                            from: 1
                            to: 100
                            onValueModified: sv.p.bgResize = value / 100
                            value: Number(sv.p.bgResize * 100).toFixed(0)
                            textFromValue: function(value, locale) {
                                return Number(value).toLocaleString(locale, "f", 0) + "%"
                            }
                            valueFromText: function(text, locale) {
                                text = text.replace(/%$/, "")
                                return Number.fromLocaleString(locale, text)
                            }
                        }
                    }
                    RowLayout {
                        Label {
                            id: l4
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "Compression:"
                        }
                        ComboBox {
                            Layout.fillWidth: true
                            id: bgCompressionComboBox
                            model: sv.p.bgCompressions
                            Component.onCompleted: currentIndex = indexOfValue(sv.p.bgCompression)
                            onActivated: sv.p.bgCompression = currentValue
                            Connections {
                                target: sv.p
                                function onBgCompressionChanged() {
                                    bgCompressionComboBox.currentIndex = bgCompressionComboBox.indexOfValue(sv.p.bgCompression)
                                }
                            }
                        }
                    }
                    RowLayout {
                        enabled: sv.p.bgCompression === "jp2" || sv.p.bgCompression === "jpeg"
                        Label {
                            id: l5
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "Quality:"
                        }
                        SpinBox {
                            Layout.fillWidth: true
                            editable: true
                            from: 1
                            to: 100
                            onValueModified: sv.p.bgQuality = value
                            value: sv.p.bgQuality
                        }
                    }
                }
            }

            GroupBox {
                Layout.fillWidth: true
                label: RowLayout {
                    width: parent.width
                    Label {
                        text: "Foreground"
                        font.bold: true
                    }
                    Switch {
                        Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                        checked: sv.p.fg
                        onToggled: sv.p.fg = checked && true
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    enabled: sv.p.fg
                    RowLayout {
                        Label {
                            id: l6
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "Colors:"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Repeater {
                                model: sv.p.fgColors
                                RowLayout {
                                    Layout.fillWidth: true
                                    Button {
                                        Layout.fillWidth: true
                                        onClicked: {
                                            colorDialog.fn = function() {
                                                sv.p.changeFgColor(index, colorDialog.color)
                                            }
                                            colorDialog.color = sv.p.fgColors[index]
                                            colorDialog.open()
                                        }
                                        Rectangle {
                                            color: parent.enabled ? paletteActive.buttonText : paletteDisabled.buttonText
                                            anchors.fill: parent
                                            anchors.margins: 5
                                            Rectangle {
                                                color: modelData
                                                anchors.fill: parent
                                                anchors.margins: 1
                                            }
                                        }
                                    }
                                    Button {
                                        Layout.fillWidth: true
                                        text: "Remove"
                                        onClicked: sv.p.removeFgColor(index)
                                    }
                                }
                            }
                            Button {
                                Layout.fillWidth: true
                                text: sv.p.fgColors.length === 0 ? "No colors" : "Add"
                                onClicked: {
                                    colorDialog.fn = function() {
                                        sv.p.addFgColor(colorDialog.color)
                                    }
                                    colorDialog.color = "#ffffff"
                                    colorDialog.open()
                                }
                            }
                        }
                    }
                    RowLayout {
                        Label {
                            id: l7
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "Compression:"
                        }
                        ComboBox {
                            Layout.fillWidth: true
                            id: fgCompressionComboBox
                            model: sv.p.fgCompressions
                            Component.onCompleted: currentIndex = indexOfValue(sv.p.fgCompression)
                            onActivated: sv.p.fgCompression = currentValue
                            Connections {
                                target: sv.p
                                function onFgCompressionChanged() {
                                    fgCompressionComboBox.currentIndex = fgCompressionComboBox.indexOfValue(sv.p.fgCompression)
                                }
                            }
                        }
                    }
                    RowLayout {
                        enabled: sv.p.fgCompression === "jbig2"
                        Label {
                            id: l8
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "JBIG2 Threshold:"
                        }
                        SpinBox {
                            Layout.fillWidth: true
                            editable: true
                            from: 40
                            to: 100
                            onValueModified: {
                                if (90 < value && value < 100) {
                                    var oldValue = Number(sv.p.fgJbig2Threshold * 100).toFixed(0)
                                    if (oldValue < value) {
                                        value = 100
                                    } else {
                                        value = 90
                                    }
                                }
                                sv.p.fgJbig2Threshold = value / 100
                            }
                            value: Number(sv.p.fgJbig2Threshold * 100).toFixed(0)
                            textFromValue: function(value, locale) {
                                return Number(value).toLocaleString(locale, "f", 0) + "%"
                            }
                            valueFromText: function(text, locale) {
                                text = text.replace(/%$/, "")
                                return Number.fromLocaleString(locale, text)
                            }
                        }
                    }
                    ColumnLayout {
                        visible: sv.p.fgCompression === "jbig2" && sv.p.fgJbig2Threshold < 1
                        Label {
                            Layout.fillWidth: true
                            font.bold: true
                            text: "Warning"
                        }
                        Label {
                            Layout.fillWidth: true
                            Layout.maximumWidth: parent.width
                            wrapMode: Label.Wrap
                            text: "Lossy JBIG2 compression can alter text in a way that is not noticeable as corruption (e.g. the numbers '6' and '8' get replaced)"
                        }
                    }
                }
            }

            GroupBox {
                label: RowLayout {
                    width: parent.width
                    Label {
                        text: "OCR"
                        font.bold: true
                    }
                    Switch {
                        Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                        checked: sv.p.ocr
                        onToggled: sv.p.ocr = checked && true
                    }
                }
                Layout.fillWidth: true

                ColumnLayout {
                    anchors.fill: parent
                    enabled: sv.p.ocr
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            id: l9
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "Language"
                        }
                        ComboBox {
                            Layout.fillWidth: true
                            id: ocrLangComboBox
                            model: sv.p.ocrLangs
                            Component.onCompleted: currentIndex = indexOfValue(sv.p.ocrLang)
                            onActivated: sv.p.ocrLang = currentValue
                            Connections {
                                target: sv.p
                                function onOcrLangChanged() {
                                    ocrLangComboBox.currentIndex = ocrLangComboBox.indexOfValue(sv.p.ocrLang)
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            id: l10
                            Layout.preferredWidth: sv.leftColumnWidth
                            text: "Colors:"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            Repeater {
                                model: sv.p.ocrColors
                                RowLayout {
                                    Button {
                                        Layout.fillWidth: true
                                        onClicked: {
                                            colorDialog.fn = function() {
                                                sv.p.changeOcrColor(index, colorDialog.color)
                                            }
                                            colorDialog.color = sv.p.ocrColors[index]
                                            colorDialog.open()
                                        }
                                        Rectangle {
                                            color: parent.enabled ? paletteActive.buttonText : paletteDisabled.buttonText
                                            anchors.fill: parent
                                            anchors.margins: 5
                                            Rectangle {
                                                color: modelData
                                                anchors.fill: parent
                                                anchors.margins: 1
                                            }
                                        }
                                    }
                                    Button {
                                        Layout.fillWidth: true
                                        text: "Remove"
                                        onClicked: sv.p.removeOcrColor(index)
                                    }
                                }
                            }
                            Button {
                                Layout.fillWidth: true
                                text: sv.p.ocrColors.length === 0 ? "All colors" : "Add"
                                onClicked: {
                                    colorDialog.fn = function() {
                                        sv.p.addOcrColor(colorDialog.color)
                                    }
                                    colorDialog.color = "#ffffff"
                                    colorDialog.open()
                                }
                            }
                        }
                    }
                }
            }
            RowLayout {
                Button {
                    Layout.fillWidth: true
                    Layout.preferredWidth: (parent.width-parent.spacing) / 2
                    text: "Apply to all"
                    onClicked: pagesModel.applyToAll(sv.p)
                }
                Button {
                    Layout.fillWidth: true
                    Layout.preferredWidth: (parent.width-parent.spacing) / 2
                    text: "Apply to following"
                    onClicked: pagesModel.applyToFollowing(sv.modelIndex, sv.p)
                }
            }
            RowLayout {
                Button {
                    Layout.fillWidth: true
                    Layout.preferredWidth: (parent.width-parent.spacing) / 2
                    text: "Load default settings"
                    onClicked: sv.p.loadUserDefaults()
                }
                Button {
                    MessageDialog {
                        id: saveUserDefaultsDialog
                        title: "Overwrite?"
                        text: "Replace default settings?"
                        icon: StandardIcon.Question
                        standardButtons: StandardButton.Yes | StandardButton.No
                        onAccepted: sv.p.saveUserDefaults()
                    }
                    Layout.fillWidth: true
                    Layout.preferredWidth: (parent.width-parent.spacing) / 2
                    text: "Save default settings"
                    onClicked: saveUserDefaultsDialog.open()
                }
            }
        }
    }
}
