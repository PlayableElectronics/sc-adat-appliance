# SC-ADAT norns controller

This is a deliberately small external OSC controller. It does not run audio on
norns and does not know scsynth node IDs. Its Lua table is mechanically rendered
from `control/generated/mixer-schema.json`. That schema is exported from the
same validated runtime configuration and control contract used by the mixer.

## Generate

From the repository root:

```sh
./lab control generate norns
```

Run this after changing the mixer configuration or control contract. It updates
the controller schema and Norns table together. To verify that committed output
is current without rewriting anything:

```sh
./lab control generate norns --check
```

Copy the resulting directory to norns as `~/dust/code/sc_adat` and rename or
copy `sc_adat.lua` to `sc_adat/sc_adat.lua` if the transfer tool does not retain
the directory layout. The final norns layout must be:

```text
~/dust/code/sc_adat/
  sc_adat.lua
  lib/mixer_contract.lua
```

The default Dell address is `192.168.1.136:57120`; norns receives replies on
its fixed OSC port `10111`.

On startup the script is read-only while it queries every exposed parameter.
Writes are enabled only after all replies arrive and the remote contract version
equals the generated contract version. `K3` performs another read-only sync.

- E1 or K2/K3: select one of eight groups or the master strip
- E2: change the selected group/master level
- E3: change master level from any selected strip

The play screen follows the visual language of norns' built-in global MIX page:
a dim target-level rail beside brighter RMS and peak bars. It is only an
overview. It reads and changes the same `params` entries described below; it
does not maintain a second set of mixer controls.

All detailed controls live in the normal norns PARAMETERS menu, grouped as
MASTER, eight named groups, and the logical sources exported by the mixer
schema. Mono sources expose linked trim/mute/polarity/HPF
controls plus pan. Stereo sources expose the same linked controls plus balance
and width instead of duplicated physical-channel controls. That menu supplies
editing, MIDI mapping and PSET save/recall without a parallel custom
implementation. Its SC-ADAT group also contains a `Sync from Dell` trigger.

Normal norns parameter-set functionality stores these parameters as presets.
Recalling a preset after synchronization invokes their actions and sends the
stored values to the Dell.

The first version intentionally omits spatial X/Y/width controls. Their JSON
ranges currently refer to `group_limits.*`, but the contract does not publish
resolved per-group limits. Adding them as unconstrained `0..1` parameters would
allow norns to request values the mixer must reject, defeating the purpose of a
schema-generated controller.
