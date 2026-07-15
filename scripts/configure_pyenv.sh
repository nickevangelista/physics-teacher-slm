#!/bin/bash
# Configure pyenv in .bashrc
set -e

BASHRC="$HOME/.bashrc"

if grep -q 'PYENV_ROOT' "$BASHRC"; then
    echo "pyenv already configured in .bashrc"
else
    cat >> "$BASHRC" << 'EOF'

# pyenv configuration
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
eval "$(pyenv virtualenv-init -)"
EOF
    echo "pyenv added to .bashrc"
fi

# Source pyenv for current script
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

echo "pyenv version: $(pyenv --version)"
echo "Installing Python 3.12..."
pyenv install 3.12 -s
echo "Python 3.12 installed successfully!"
pyenv versions
