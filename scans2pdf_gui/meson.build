pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'scans2pdf_gui'

conf = configuration_data()
conf.set('PYTHON', python.full_path())
conf.set_quoted('localedir', get_option('prefix') / get_option('localedir'))
conf.set_quoted('pkgdatadir', pkgdatadir)

scans2pdf_gui_bin = configure_file(
  input: 'scans2pdf-gui.in',
  output: 'scans2pdf-gui',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x',
)

scans2pdf_gui_sources = files([
  '__init__.py',
  'main.py',
])

install_data(scans2pdf_gui_sources, install_dir: moduledir)


subdir('qml')
