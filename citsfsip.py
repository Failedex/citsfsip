#! /usr/bin/env python3
from i3ipc import Connection, Rect, Event
import time
import subprocess
import math
import threading
import json
from iconfetch import fetch

class Workspace():
    def __init__(self, name, rect):
        self.name = name
        self.stack = None
        self.count = 0
        self.screen = rect
        self.next = None
        self.ratio = 0.5

class Window(Rect):
    def __init__(self, data, pid):
        self.pid = pid
        self.next = None
        self.icon = None
        self.name = "idk"
        super().__init__(data)

    def __eq__(self, other):
        if not other:
            return False

        if self.x != other.x:
            return False
        if self.y != other.y:
            return False
        if self.width != other.width:
            return False
        if self.height != other.height:
            return False
        return True

    def set(self, x = None, y = None, width = None, height = None):
        margin = 5 
        if x is not None:
            self.x = x + margin
        if y is not None:
            self.y = y + margin + 40
        if width is not None:
            self.width = width - 2*margin
        if height is not None:
            self.height = height - 2*margin -40

    def move(self, a:Rect, dx:float):
        global focused_pid

        x = a.x + (self.x-a.x)*dx
        y = a.y + (self.y-a.y)*dx
        width = a.width + (self.width-a.width)*dx
        height = a.height + (self.height-a.height)*dx

        i3.command(f"[pid={self.pid}] move absolute position {int(x)}px {int(y)}px")
        i3.command(f"[pid={self.pid}] resize set width {int(width)}px height {int(height)}px")
        return dict(
            pid = self.pid,
            icon = self.icon,
            name = self.name,
            focused = self.pid == focused_pid,
            x = int(x)-1440,
            y = int(y),
            width = int(width),
            height = int(height)
        )

    def exist(self):
        return len(i3.get_tree().find_by_pid(self.pid)) > 0

def move_all():
    global workspaces
    name = workspaces.name
    stack = workspaces.stack
    # get all current positions and goal positions
    current = []
    target = []

    cur = stack 
    while cur != None:
        win = i3.get_tree().find_by_pid(cur.pid)
        if len(win) == 0:
            return
        win[0].rect.y -= win[0].deco_rect.height
        win[0].rect.height += win[0].deco_rect.height
        current.append(win[0].rect)
        target.append(Window(dict(
            x = cur.x,
            y = cur.y,
            width = cur.width,
            height = cur.height
        ), cur.pid))

        cur = cur.next

    start = time.time()
    for i in range(60):
        t = time.time()-start 
        # exponential decay
        # dx = 1 - math.exp(-15*t)
        a = -5.2
        b = 7.6
        dx = 1-(math.exp(a*t)*math.cos(b*t))+0.5*(math.exp(a*t)*math.sin(b*t))

        if i >= 59:
            dx = 1

        cur = stack
        j = 0
        data = []
        while cur != None:
            if cur.pid != target[j].pid:
                return

            if cur != target[j]:
                return 

            if workspaces.name != name:
                return

            data.append(cur.move(current[j], dx))

            j += 1
            cur = cur.next

        print(json.dumps(data), flush=True)

        time.sleep(1/60)

    
def eval_stack():
    global workspaces
    global anim
    stack = workspaces.stack
    screen = workspaces.screen   

    cur = stack
    prev = None
    while cur != None: 
        if not cur.exist():
            if prev:
                prev.next = cur.next 
            else:
                workspaces.stack = cur.next
            workspaces.count -= 1 

        prev = cur
        cur = cur.next

    if workspaces.count == 0:
        print(json.dumps([]), flush=True)
        return

    cur = workspaces.stack
    cur.set(
        x = screen.x, 
        y = screen.y, 
        width = screen.width, 
        height = screen.height
    )

    if workspaces.count > 1:
        cur.set(width = cur.width*workspaces.ratio)
        cur = cur.next 
        j = 0
        h = screen.height//(workspaces.count-1)
        while cur != None:
            cur.set(
                y = screen.y + j*h,
                x = screen.x + (screen.width*workspaces.ratio) + 1,
                width = screen.width*(1-workspaces.ratio),
                height = h
            )
            cur = cur.next
            j += 1

    if anim.is_alive():
        anim.join()

    anim = threading.Thread(target=move_all)
    anim.start()

def new_workspace(name, rect):
    global workspaces
    cur = workspaces
    prev = None
    while cur != None:
        if cur.name == name:
            return cur
        prev = cur
        cur = cur.next
    if prev == None:
        workspaces = Workspace(name, rect)
        return workspaces
    prev.next = Workspace(name, rect)
    return prev.next

def add_win(pid, x, y, width, height, workspace=None, icon=fetch("unknown"), name="idk"):
    global workspaces
    if workspace == None:
        workspace = workspaces

    data = dict (
        x = x,
        y = y,
        width = width,
        height = height
    )

    new = Window(data, pid)
    new.icon = icon
    new.name = name

    if workspace.stack:
        new.next = workspace.stack 

    workspace.count += 1

    workspace.stack = new

def workspace(i3, e):
    global workspaces

    # finding focused
    cur = workspaces
    prev = None
    while cur != None and cur.name != e.current.name:
        prev = cur
        cur = cur.next

    if not cur:
        # e.current.rect doesn't fucking work
        for o in i3.get_workspaces():
            if o.name == e.current.name:
                cur = new_workspace(e.current.name, o.rect)
    if prev:
        prev.next = cur.next
        cur.next = workspaces
        workspaces = cur
    
    eval_stack()

def new(i3, e):
    cur = i3.get_tree().find_focused()
    add_win(cur.pid, 0, 0, 100, 100, None, fetch(cur.app_id) or fetch("unknown"), cur.name)
    eval_stack()

def close(i3, e):
    eval_stack()

def mark(i3, e):
    global workspaces
    stack = workspaces.stack

    tree = i3.get_tree()

    res = tree.find_marked("master")

    def prev_cur(res):
        m = res[0]
        i3.command(f"[pid={m.pid}] unmark")
        
        cur = stack
        prev = None
        while cur != None and cur.pid != m.pid:
            prev = cur
            cur = cur.next

        return (prev, cur)

    if len(res) == 1:
        prev, cur = prev_cur(res)

        if not cur or not prev:
            return

        prev.next = cur.next
        cur.next = stack 
        workspaces.stack = cur

        eval_stack()
        return

    res = tree.find_marked("up")
    if len(res) == 1:
        prev, cur = prev_cur(res)

        if not prev:
            prev = cur
            while prev.next != None:
                prev = prev.next

        i3.command(f"[pid={prev.pid}] focus")
        return

    res = tree.find_marked("down")
    if len(res) == 1:
        _, cur = prev_cur(res)

        front = cur.next
        if not front:
            front = stack

        i3.command(f"[pid={front.pid}] focus")
        return

    res = tree.find_marked("incm")
    if len(res) == 1:
        m = res[0]
        i3.command(f"[pid={m.pid}] unmark")
        workspaces.ratio -= 0.02
        eval_stack()
        return

    res = tree.find_marked("decm")
    if len(res) == 1:
        m = res[0]
        i3.command(f"[pid={m.pid}] unmark")
        workspaces.ratio += 0.02
        eval_stack()
        return

def movewin(i3, e):
    global workspaces
    pid = e.container.pid or None
    if pid == None:
        return

    # remove from current workspace
    cur = workspaces.stack
    prev = None
    while cur != None:
        if cur.pid == pid:
            if prev:
                prev.next = cur.next
            else:
                workspaces.stack = cur.next
            workspaces.count -= 1
        prev = cur
        cur = cur.next

    # move to new workspace
    for w in i3.get_tree().workspaces():
        for n in w.floating_nodes:
            if n.pid == pid:
                ws = new_workspace(w.name, w.rect)
                add_win(pid, 0, 0, 100, 100, ws, fetch(n.app_id) or fetch("unknown"), n.name)

    eval_stack()

# def focus(i3, e):
#     global focused_pid
#     if e.container.pid:
#         focused_pid = e.container.pid
#     eval_stack()

if __name__ == "__main__":
    workspaces = None
    i3 = Connection()
    anim = threading.Thread(target=move_all)
    margin = 10
    focused_pid = 0

    i3.command("bindsym Mod4+k mark 'up'")
    i3.command("bindsym Mod4+j mark 'down'")
    i3.command("bindsym Mod4+h mark 'incm'")
    i3.command("bindsym Mod4+l mark 'decm'")
    i3.command("bindsym Mod4+Shift+Return mark 'master'")

    # animation looks better when window comes from top
    i3.command("for_window [app_id=.*] move up 800px")

    # get outputs screens
    for o in i3.get_tree().nodes: 
        if o.name == "__i3":
            continue

        for w in o.nodes:
            wo = new_workspace(w.name, w.rect)
            for l in w.floating_nodes:
                add_win(l.pid, 0, 0, 100, 100, wo)
                    
            if w.focused:
                wo.next = workspaces
                workspaces = wo

    eval_stack()

    i3.on(Event.WINDOW_NEW, new)
    i3.on(Event.WINDOW_CLOSE, close)
    i3.on(Event.WINDOW_MARK, mark)
    i3.on(Event.WINDOW_MOVE, movewin)
    # i3.on(Event.WINDOW_FOCUS, focus)
    i3.on(Event.WORKSPACE_FOCUS, workspace)

    try:
        i3.main()
    finally:
        i3.command("for_window [app_id=.*] move center")
