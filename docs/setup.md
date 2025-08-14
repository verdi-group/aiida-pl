---
jupyter:
  jupytext:
    default_lexer: ipython3
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.17.2
  kernelspec:
    display_name: DEFECT
    language: python
    name: python3
---

# Setup

Before running the workflows in the `aiida-pl` package, you need to set up the computers, codes and pseudo potentials.
This notebook takes you through all the necessary steps to do so.

```python
from aiida import orm, load_profile
from aiida.common.exceptions import NotExistent

load_profile()
```

```{margin}
⚠️ Always execute this cell before any cell in the rest of this notebook!
```

<!-- #region -->


## Computers

First we'll set up the computers for AiiDA to run on.
For this AiiDA needs to know the "working directory" on the remote computer

```{important}
Most of the cells in this notebook can be executed blindly, but in some cases you have adapt the cell content depending on your username on Pawsey etc.
**For example, you need to update the `working_directory` in the cell below to the root directory on `/scratch` where you want to run your AiiDA calculations.**
All cells that need to be adapted will have a warning (e.g. "⚠️ **Adapt the path here!**") in the side bar on the right.
```
<!-- #endregion -->

```python
working_directory = '/scratch/pawsey1141/mbercx/aiida-defect/aiida'
```

```{margin}
⚠️ **Adapt the path here!**
```

The cell below configures two computers:

* `pawsey`: The default `pawsey` computer, configured for the slurm (`core.slurm`) scheduler.
* `pawsey-direct`: Almost the same, but uses the `core.direct` scheduler.

The "transport" that we'll use (identified via `core.ssh_async`) will automatically use the configuration from your `~/.ssh/config`.
Hence the instructions below assume that you've already set up you connection with the computer.

```python
try:
    pawsey = orm.load_computer('pawsey')
except NotExistent:
    pawsey = orm.Computer(
        label='pawsey',
        hostname='setonix.pawsey.org.au',
        transport_type='core.ssh_async',
        scheduler_type='core.slurm',
    )
    pawsey.set_workdir(working_directory)
    pawsey.set_mpirun_command('srun -N {num_machines} -n {tot_num_mpiprocs} -c 1 -m block:block:block'.split())
    pawsey.set_default_mpiprocs_per_machine(64)
    pawsey.set_use_double_quotes(True)
    pawsey.configure()
    pawsey.store()

try:
    pawsey_direct = orm.load_computer('pawsey-direct')
except NotExistent:
    pawsey_direct = orm.Computer(
        label='pawsey-direct',
        hostname='setonix.pawsey.org.au',
        transport_type='core.ssh_async',
        scheduler_type='core.direct',
    )
    pawsey_direct.set_workdir(working_directory)
    pawsey_direct.set_default_mpiprocs_per_machine(1)
    pawsey_direct.set_use_double_quotes(True)
    pawsey_direct.configure()
    pawsey_direct.store()
```

```{note}
The code snippets for setting up the computers are wrapped in `try-except` blocks to avoid trying to set up the same computer multiple times.
This would fail, since two computers can't have the same label.
```

We can see if the computers have been set up properly using the CLI command:

```python
!verdi computer list
```

As well as test them:

```python
!verdi computer test pawsey
```

## Codes

Next, we'll set up the VASP codes we need to run on `pawsey`.
We'll need to run both the `vasp_gam` and `vasp_std` version, which we'll set up as separate codes:

```python
try:
    orm.load_code('vasp-6.5.1_gam@pawsey')
except NotExistent:
    code = orm.InstalledCode(
        label='vasp-6.5.1_gam',
        computer=pawsey,
        default_calc_job_plugin='vasp.vasp',
        filepath_executable='/software/projects/pawsey1141/cverdi/vasp.6.5.1/bin/vasp_gam'
    )
    code.description = 'VASP 6.5.1 gamma version'
    code.use_double_quotes = True
    code.prepend_text = """
module load hdf5/1.14.3-api-v112 netlib-scalapack/2.2.0 fftw/3.3.10
export OMP_NUM_THREADS=1
export MPICH_OFI_STARTUP_CONNECT=1
export MPICH_OFI_VERBOSE=1
export FI_CXI_DEFAULT_VNI=$(od -vAn -N4 -tu < /dev/urandom)
ulimit -s unlimited
"""
    code.store()

try:
    orm.load_code('vasp-6.5.1_std@pawsey')
except NotExistent:
    code = orm.InstalledCode(
        label='vasp-6.5.1_std',
        computer=pawsey,
        default_calc_job_plugin='vasp.vasp',
        filepath_executable='/software/projects/pawsey1141/cverdi/vasp.6.5.1/bin/vasp_std'
    )
    code.description = 'VASP 6.5.1 gamma version'
    code.use_double_quotes = True
    code.prepend_text = """
module load hdf5/1.14.3-api-v112 netlib-scalapack/2.2.0 fftw/3.3.10
export OMP_NUM_THREADS=1
export MPICH_OFI_STARTUP_CONNECT=1
export MPICH_OFI_VERBOSE=1
export FI_CXI_DEFAULT_VNI=$(od -vAn -N4 -tu < /dev/urandom)
ulimit -s unlimited
"""
    code.store()
```

We need to be able to calculate the transition dipole moments (TDMs) using `vaspkit`.
The simple `bash` script below wraps `vaspkit` to calculate all TDMs for a range of "target levels"

```{important}
The script below assumes that you have installed `vaspkit` on the remote computer, and that the binary is available in your default `PATH`.
```

```python
vaspkit_script = """
#!/usr/bin/env bash
set -e

MIN_INDEX="$1"
MAX_INDEX="$2"
TARGET_DIR="$3"

CURR_DIR="$(pwd)"

if [ -n "$TARGET_DIR" ]; then
    cd "$TARGET_DIR"
fi

for target_level in $(seq "$MIN_INDEX" "$MAX_INDEX"); do
    for source_level in $(seq 1 $((target_level - 1))); do
        echo "Running vaspkit for index $idx..."
        (
            echo -e "71\n713\n0\n${source_level} ${target_level}\n1" | vaspkit
            echo "$source_level $target_level" >> "$CURR_DIR/tdm_dw.dat"
            echo "$source_level $target_level" >> "$CURR_DIR/tdm_up.dat"
            cat TDM_COMPONENTS_DW.dat >> "$CURR_DIR/tdm_dw.dat"
            cat TDM_COMPONENTS_UP.dat >> "$CURR_DIR/tdm_up.dat"
        )
    done
done

if [ -n "$TARGET_DIR" ]; then
    cd "$CURR_DIR"
fi

"""
```

```{note}
Feel free to have a look at the script in case you want to understand it, but you don't need to in order to run the workflows.
```

In our current approach, the script needs to be available on the remote machine.
We could also copy the script for every execution, but that seems unnecessary.
The cells below take care of copying the script to the remote and 

```python
script_directory = '/home/mbercx/aiida-scripts'
script_filename = 'get_tdm.sh'
```

```{margin}
⚠️ **Adapt the path here!**
```

```python
from pathlib import Path

script_directory = Path(script_directory)
tdm_script_path = Path(script_filename).absolute()

with tdm_script_path.open('w') as handle:
    handle.write(vaspkit_script)

with pawsey.get_transport() as transport:
    transport.makedirs(script_directory, ignore_existing=True)
    transport.put(tdm_script_path, script_directory)
    transport.chmod(script_directory / script_filename, 0o700)
```

```python
from aiida_shell import ShellCode

try:
    orm.load_code('get_tdm@pawsey-direct')
except NotExistent:
    code = ShellCode(
        label='get_tdm',
        computer=pawsey_direct,
        filepath_executable=f'{script_directory}/{script_filename}'
    )
    code.use_double_quotes = True
    code.store()
```

Let's make sure we have all codes set up properly!

```python
!verdi code list
```

You should see something along the lines of:

```
Full label               Pk  Entry point
---------------------  ----  -------------------------
vasp-6.5.1_gam@pawsey     1  core.code.installed
vasp-6.5.1_std@pawsey     2  core.code.installed
get_tdm@pawsey-direct     3  core.code.installed.shell
```


## Pseudo potentials


In order to set up the input `POTCAR` files, the `aiida-vasp` plugin needs access to the VASP pseudo potentials.

```python
path_to_potcar_files = '/Users/mbercx/tmp/potpaw'
```

```{sidebar}
⚠️ **Adapt the path here!**
```


The cell below loads the pseudo potentials from the path specified above.
Since you can only upload them once, we once again wrap the cell in a `try`-`except` block.

```python
from aiida_vasp.data.potcar import PotcarData

try:
    orm.load_group('PBE.64')
except NotExistent:
    PotcarData.upload_potcar_family(
        source=path_to_potcar_files,
        group_name='PBE.64',
        group_description='Family of the v64 pseudo potentials for VASP.'
    );
```
We can confirm that the pseudo potentials have been installed properly using:

```python
!verdi data vasp.potcar listfamilies

```

You should see `PBE.64` among the list of families.
If so, time to move on to the "Energy levels workflow"!



