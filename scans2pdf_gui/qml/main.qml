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

import QtQuick
import QtQuick.Controls

ApplicationWindow {
    SystemPalette { id: paletteActive; colorGroup: SystemPalette.Active }
    SystemPalette { id: paletteDisabled; colorGroup: SystemPalette.Disabled }
    visible: true
    width: 640
    height: 480
    title: N_("Scans to PDF")

    StackView {
        id: stack
        initialItem: "overview.qml"
        anchors.fill: parent
    }
}
