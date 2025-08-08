# Usage:
#   just_uv.sh --py3.x
#
#   --py3.x: Python version for the virtual environment (e.g., --py3.12).

VENV_PYTHON_VERSION=3.12

while [[ $# -gt 0 ]]; do
  case "$1" in
    --py3.*)
      VENV_PYTHON_VERSION="${1#--py}"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "UV not found. Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    check_status "UV installation"

    # Add UV to PATH and make it persistent (add both potential UV installation locations)
    export PATH="/root/.local/bin:/root/.cargo/bin:$HOME/.local/bin:$PATH"
    echo 'export PATH="/root/.local/bin:/root/.cargo/bin:$HOME/.local/bin:$PATH"' >> ~/.bashrc
    # Also add to .profile to ensure it's available in all shells
    echo 'export PATH="/root/.local/bin:/root/.cargo/bin:$HOME/.local/bin:$PATH"' >> ~/.profile

    # Source both files to ensure immediate availability
    source ~/.bashrc
    source ~/.profile

    # Verify UV installation more thoroughly
    which uv || { echo "UV is not in PATH. Installation failed." >&2; exit 1; }
    uv --version || { echo "UV installation is broken." >&2; exit 1; }
fi

echo "Setting up virtual environment with Python version ${VENV_PYTHON_VERSION}..."
uv venv .venv --python="${VENV_PYTHON_VERSION}"