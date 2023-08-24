project('djpdfgui',
  version: '0.5.2',
  meson_version: '>= 0.62.0',
  default_options: ['warning_level=2', 'werror=false'],
)

i18n = import('i18n')
python = import('python').find_installation('python3')
merge_xml_aux = meson.current_source_dir() / 'build-aux' / 'meson' / 'merge-xml.py'
move_aux = meson.current_source_dir() / 'build-aux' / 'meson' / 'move.py'

subdir('desktop')
subdir('scans2pdf_gui')
subdir('po')
