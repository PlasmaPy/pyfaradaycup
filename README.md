# pyFaradayCup

An open source Python package for data reduction and analysis of Faraday Cup measurements of heliospheric plasma, in the early stages of development.

## Installation from source into a virtual environment

1. [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

2. Clone the repository, such as with:

   ```shell
   git clone https://github.com/PlasmaPy/pyfaradaycup.git
   ```

3. Create a virtual environment in the directory.

   ```shell
   cd pyfaradaycup
   uv venv
   ```

4. Activate the virtual environment for your shell, using the command printed out from the previous command.

   ```shell
   source .venv/bin/activate  # POSIX compliant shells like bash, zsh, and sh
   source .venv/bin/activate.csh  # csh, tcsh
   source .venv/bin/activate.fish  # fish
   .venv\Scripts\activate  # Windows
   ```

   > [!NOTE]
   > This command will need to be repeated if you open a new terminal window.

5. Install the package into the virtual environment with:

   ```shell
   uv pip install -e .
   ```
   The `-e` is short for `--editable`.
