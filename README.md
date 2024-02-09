# Completely impractical tiling system for sway in particular (citsfsip)
This "simple" script mimics dynamic tiling (dwm) tiling on sway, it also adds window animations. Like the name suggest, it wasn't made to be practical. Rather, it was made because it was possible.

## Dependencies
- python3
- i3ipc python

## Reasons not to use citsfsip
- The name sucks
- Hacky animations
- Impractical
- No floating windows (kinda)

## Set up
```
# Make every window floating. Citsfsip manages tiling itself.
for_window [app_id=.*] floating enable

# Default dwm bindings
# Marking a window up or down will shift the focus on stack
bindsym $mod+k mark 'up'
bindsym $mod+j mark 'down'

# Increasing or decreasing master
bindsym $mod+h mark 'incm'
bindsym $mod+l mark 'decm'

# Promoting window to master
bindsym $mod+Shift+Return mark 'master'

# Run script here or run script manually
exec $HOME/where/the/script/is
```
