# Future milestone: Virtual Dyaxis control surface

Status: planned; specification and tracking only. This milestone is not
implemented in the current native RT candidate work.

The immediate priority remains booting the native candidate and producing the
first controlled SuperCollider sound on the DIGI9652.

## Scope

The milestone will deliver a virtual control surface approximating the
eight-fader Dyaxis workflow, with a software design that can later drive the
physical bridge. It includes:

- an Open Stage Control layout with eight primary faders;
- a canonical, versioned OSC mixer protocol;
- bidirectional synchronization around one authoritative mixer state;
- explicit 24-channel banking and bank/channel addressing;
- faders, encoders, buttons and a jog wheel;
- routing, monitoring, effects and looping controls;
- compatibility targets for Open Stage Control, TouchOSC, norns and the
  eventual physical Dyaxis bridge.

## Design requirements

The protocol must define message names, argument types, ranges, units,
timestamps or ordering rules, capability discovery and version negotiation.
Clients must be able to receive the complete authoritative state and apply
incremental updates without inventing conflicting local mixer state. Bank
selection and channel identity must remain explicit so a 24-channel mixer
cannot silently address the wrong eight-channel view.

The control layout and protocol should keep transport independent from client
presentation. Open Stage Control and TouchOSC are visual clients; norns is a
scriptable client; the physical bridge is a hardware adapter. All four must
consume the same versioned mixer semantics.

## Future completion gates

Before implementation is considered complete, the repository should contain:

1. a versioned OSC protocol document and machine-readable message fixtures;
2. the Open Stage Control eight-fader layout;
3. authoritative-state and reconnect/synchronization tests;
4. 24-channel banking tests, including boundary channels and bank changes;
5. compatibility checks for Open Stage Control, TouchOSC, norns and the
   physical-bridge adapter boundary;
6. exercised controls for mixing, routing, monitoring, FX, looping and jog
   behavior.

No control-surface implementation, protocol endpoint or client asset is part
of the current RT candidate milestone.
