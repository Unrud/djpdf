desktop_file = i18n.merge_file(
  input: 'com.github.unrud.djpdf.desktop.in',
  output: 'com.github.unrud.djpdf.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications',
)

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils,
    args: [desktop_file],
  )
endif

base_appstream_file = i18n.merge_file(
  input: 'com.github.unrud.djpdf.metainfo.xml.in',
  output: 'com.github.unrud.djpdf-base.metainfo.xml',
  po_dir: '../po',
)

appstream_file = custom_target('com.github.unrud.djpdf.metainfo.xml',
  input: [
    base_appstream_file,
    'com.github.unrud.djpdf.metainfo-releases.xml.in',
  ],
  output: 'com.github.unrud.djpdf.metainfo.xml',
  command: [
    python, merge_xml_aux,
    '@INPUT0@', '@INPUT1@', '.',
  ],
  capture: true,
  install: true,
  install_dir: get_option('datadir') / 'metainfo',
)

appstream_util = find_program('appstream-util', required: false)
if appstream_util.found()
  test('Validate appstream file', appstream_util,
    args: ['validate-relax', appstream_file],
  )
endif

icon_id = 'com.github.unrud.djpdf'
icon_src = icon_id + '.png'
convert_util = find_program('convert')
foreach res : [16, 32, 48, 64, 128, 256, 512]
  icon_install_dir = (
    get_option('datadir') / 'icons' / 'hicolor' / '@0@x@0@'.format(res) / 'apps'
  )
  icon_png = '@0@_@1@.png'.format(icon_id, res)
  custom_target(icon_png,
    input: icon_src,
    output: icon_png,
    command: [
      convert_util,
      '+set', 'date:create', '+set', 'date:modify',
      '@INPUT@', '-resize', '@0@x@0@'.format(res), '@OUTPUT@',
    ],
    install: true,
    install_dir: icon_install_dir,
  )
  # rename icon after installation
  meson.add_install_script(python, move_aux,
    icon_install_dir / icon_png,
    icon_install_dir / icon_id + '.png',
  )
endforeach
