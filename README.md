# Completely impractical tiling system for sway in particular (citsfsip)
This "simple" script mimics dynamic tiling (dwm) tiling on sway, it also adds window animations. Like the name suggest, it wasn't made to be practical. Rather, it was made because it was possible.

> [!TIP]
> If you're (for whatever reason) thinking of using this repo as a reference... maybe take a walk, clear your head, and reconsider.
> Still, if you insist, I recommend taking a look at the successor [SniriFX](https://github.com/Failedex/SniriFX), which is slightly more presentable.

https://github.com/Failedex/citsfsip/assets/92513573/8dc0490b-3bc8-4e81-ad2b-45fab7474dae


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
# Default dwm bindings
# Marking a window up or down will shift the focus on stack
bindsym $mod+k mark '_up'
bindsym $mod+j mark '_down'

# Increasing or decreasing master
bindsym $mod+h mark '_incm'
bindsym $mod+l mark '_decm'

# Promoting window to master
bindsym $mod+Shift+Return mark '_master'

# Run script here or run script manually
exec $HOME/where/the/script/is
```
