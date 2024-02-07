#! /usr/bin/env python3
from i3ipc import Connection, Rect, Event
import time
import subprocess
import math
import threading

class Workspace():
    def __init__(self, name, rect):
        self.name = name
        self.stack = None
        self.count = 0
        self.screen = rect
        self.next = None

class Window(Rect):
    def __init__(self, data, pid):
        self.pid = pid
        self.next = None
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
            self.y = y + margin
        if width is not None:
            self.width = width - 2*margin
        if height is not None:
            self.height = height - 2*margin

    def move(self, a:Rect, dx:float):

        a.x += (self.x-a.x)*dx
        a.y += (self.y-a.y)*dx
        a.width += (self.width-a.width)*dx
        a.height += (self.height-a.height)*dx

        i3.command(f"[pid={self.pid}] move absolute position {int(a.x)}px {int(a.y)}px")
        i3.command(f"[pid={self.pid}] resize set width {int(a.width)}px height {int(a.height)}px")

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
    for i in range(25):
        t = time.time()-start 
        # exponential decay
        dx = 1 - math.exp(-5*t)

        if i == 24:
            dx = 1

        cur = stack
        j = 0
        while cur != None:
            if cur.pid != target[j].pid:
                return

            if cur != target[j]:
                return 

            if workspaces.name != name:
                return

            cur.move(current[j], dx)

            j += 1
            cur = cur.next

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
            # remove 
            if prev:
                prev.next = cur.next 
            else:
                workspaces.stack = cur.next

            workspaces.count -= 1 

        prev = cur
        cur = cur.next

    if workspaces.count == 0:
        return

    cur = workspaces.stack
    cur.set(
        x = screen.x, 
        y = screen.y, 
        width = screen.width, 
        height = screen.height
    )

    if workspaces.count > 1:
        cur.set(width = cur.width//2)
        cur = cur.next 
        j = 0
        h = screen.height//(workspaces.count-1)
        while cur != None:
            cur.set(
                y = screen.y + j*h,
                x = screen.x + (screen.width//2) + 1,
                width = screen.width//2,
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

def add_win(pid, x, y, width, height, workspace=None):
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
    add_win(cur.pid, 0, 0, 100, 100)
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


if __name__ == "__main__":
    workspaces = None
    i3 = Connection()
    anim = threading.Thread(target=move_all)
    margin = 10

    i3.command("bindsym Mod4+k mark 'up'")
    i3.command("bindsym Mod4+j mark 'down'")
    i3.command("bindsym Mod4+Shift+Return mark 'master'")
    i3.command("for_window [app_id=.*] floating enable")

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
    i3.on(Event.WORKSPACE_FOCUS, workspace)

    try:
        i3.main()
    finally:
        i3.command("for_window [app_id=.*] move center")
