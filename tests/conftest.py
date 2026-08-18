import sys
from pathlib import Path

# Asegura que la raíz del proyecto sea importable
# sin importar desde qué directorio se invoque pytest.
sys.path.insert(0, str(Path(__file__).parent.parent))
