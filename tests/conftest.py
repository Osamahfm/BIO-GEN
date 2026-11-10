"""Use an isolated case store before any application module is imported."""
import os
import tempfile
os.environ['BIOGEN_DATA_DIR']=tempfile.mkdtemp(prefix='biogen-pytest-isolated-')

os.environ['BIOGEN_OFFLINE']='1'
