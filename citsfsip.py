#! /usr/bin/env python3
from i3ipc import Rect, Event
from i3ipc.aio import Connection
import time
import math
import asyncio

class Workspace():
    def __init__(self, name, rect):
        self.name = name
        self.stack = None
        self.count = 0
        self.screen = rect
        self.next = None
        self.ratio = 0.5

    async def find_window(self, pid): 
        cur = self.stack 
        prev = None 
        while cur != None and cur.pid != pid:
            prev = cur 
            cur = cur.next
        
        return (cur, prev)

    async def add_win(self, pid):
        new = Window(dict(
            x = 0, 
            y = 0, 
            width = 100, 
            height = 100
        ), pid)

        if self.stack:
            new.next = self.stack

        self.count += 1
        self.stack = new

    async def eval_stack(self, i3):
        global animid
        cur = self.stack 
        prev = None 
        tree = await i3.get_tree()
        while cur != None:
            if len(tree.find_by_pid(cur.pid)) == 0:
                # removal
                if prev:
                    prev.next = cur.next 
                else: 
                    self.stack = cur.next

                self.count -= 1

            prev = cur 
            cur = cur.next

        animid += 1

        if self.count == 0:
            return

        screen = self.screen
        cur = self.stack 
        await cur.set(
            x = screen.x,
            y = screen.y,
            width = screen.width,
            height = screen.height
        )

        if self.count > 1:
            await cur.set(width = cur.width*self.ratio)
            cur = cur.next 
            j = 0
            h = screen.height//(self.count-1)
            
            while cur != None:
                await cur.set(
                    y = screen.y + j*h,
                    x = screen.x + (screen.width*self.ratio) + 1,
                    width = screen.width*(1-self.ratio),
                    height = h
                )

                cur = cur.next
                j += 1

        # play animation
        await self.move_all(i3)


    async def move_all(self, i3):
        global animid 
        # if another animation starts running, this one will be cancelled
        id = animid

        current = []

        cur = self.stack 
        tree = await i3.get_tree()
        while cur != None:
            win = tree.find_by_pid(cur.pid)
            if len(win) == 0:
                return

            win[0].rect.y -= win[0].deco_rect.height
            win[0].rect.height += win[0].deco_rect.height
            current.append(win[0].rect)

            cur = cur.next

        start = time.time()

        frames = 25

        for i in range(frames):
            t = time.time()-start

            # exponential decay
            dx = 1 - math.exp(-15*t)

            # a = -5.2
            # b = 7.6
            # dx = 1-(math.exp(a*t)*math.cos(b*t))+0.5*(math.exp(a*t)*math.sin(b*t))

            if i == frames-1:
                dx = 1

            cur = self.stack
            j = 0 
            while cur != None:
                if animid != id:
                    return

                await cur.move(i3, current[j], dx)
                j += 1
                cur = cur.next

            # manual cap at 60hz
            await asyncio.sleep(1/60)

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

    async def set(self, x = None, y = None, width = None, height = None):
        margin = 5 
        if x is not None:
            self.x = x + margin
        if y is not None:
            self.y = y + margin
        if width is not None:
            self.width = width - 2*margin
        if height is not None:
            self.height = height - 2*margin

    async def move(self, i3, a, dx):
        x = a.x + (self.x-a.x)*dx
        y = a.y + (self.y-a.y)*dx
        width = a.width + (self.width-a.width)*dx
        height = a.height + (self.height-a.height)*dx

        await i3.command(f"[pid={self.pid}] resize set width {int(width)}px height {int(height)}px")
        await i3.command(f"[pid={self.pid}] move absolute position {int(x)}px {int(y)}px")

class Citsfsip:
    def __init__(self):
        self.i3 = None
        self.workspace = None
        
    async def setup(self):
        self.i3 = await Connection().connect()

        # await self.i3.command("bindsym Mod4+k mark 'up'")
        # await self.i3.command("bindsym Mod4+j mark 'down'")
        # await self.i3.command("bindsym Mod4+h mark 'incm'")
        # await self.i3.command("bindsym Mod4+l mark 'decm'")
        # await self.i3.command("bindsym Mod4+Shift+Return mark 'master'")
        # await self.i3.command("for_window [app_id=.*] floating enable")

        tree = await self.i3.get_tree()

        for w in tree.workspaces():
            wo = await self.get_workspace(w.name, w.rect)
            
            for l in w.floating_nodes:
                await wo.add_win(l.pid)

        self.i3.on(Event.WINDOW_NEW, self.window_new)
        self.i3.on(Event.WINDOW_CLOSE, self.window_close)
        self.i3.on(Event.WINDOW_MARK, self.window_mark)
        self.i3.on(Event.WINDOW_MOVE, self.window_move)
        self.i3.on(Event.WORKSPACE_FOCUS, self.workspace_focus)
        await self.i3.main()

    async def window_new(self, i3, e):
        tree = await i3.get_tree()
        cur = tree.find_focused()
        await self.workspace.add_win(cur.pid)
        await self.workspace.eval_stack(i3)

    async def window_close(self, i3, e):
        await self.workspace.eval_stack(i3)

    async def window_mark(self, i3, e):
        stack = self.workspace.stack 

        tree = await i3.get_tree()
        
        res = tree.find_marked("master")

        if len(res) == 1:
            m = res[0]
            await i3.command(f"[pid={m.pid}] unmark")
            cur, prev = await self.workspace.find_window(m.pid)

            if not cur or not prev:
                return 

            prev.next = cur.next
            cur.next = self.workspace.stack
            self.workspace.stack = cur

            await self.workspace.eval_stack(i3)
            return 

        res = tree.find_marked("up")
        if len(res) == 1:
            m = res[0]
            await i3.command(f"[pid={m.pid}] unmark")
            cur, prev = await self.workspace.find_window(m.pid)

            if not prev:
                prev = cur 
                while prev.next != None:
                    prev = prev.next

            await i3.command(f"[pid={prev.pid}] focus")
            return

        res = tree.find_marked("down")
        if len(res) == 1:
            m = res[0]
            await i3.command(f"[pid={m.pid}] unmark")
            cur, _ = await self.workspace.find_window(m.pid)

            front = cur.next 
            if not front:
                front = self.workspace.stack

            await i3.command(f"[pid={front.pid}] focus")
            return

        res = tree.find_marked("incm")
        if len(res) == 1:
            m = res[0]
            await i3.command(f"[pid={m.pid}] unmark")
            self.workspace.ratio -= 0.02
            await self.workspace.eval_stack(i3)
            return

        res = tree.find_marked("decm")
        if len(res) == 1:
            m = res[0]
            await i3.command(f"[pid={m.pid}] unmark")
            self.workspace.ratio += 0.02
            await self.workspace.eval_stack(i3)
            return

    async def window_move(self, i3, e):
        pid = e.container.pid or None
        if pid == None:
            return

        cur = self.workspace.stack 
        prev = None
        while cur != None:
            if cur.pid == pid:
                if prev:
                    prev.next = cur.next
                else: 
                    self.workspace.stack = cur.next
                self.workspace.count -= 1
            prev = cur 
            cur = cur.next

        tree = await i3.get_tree()
        for w in tree.workspaces():
            for n in w.floating_nodes: 
                if n.pid == pid:
                    ws = await self.get_workspace(w.name, w.rect)
                    await ws.add_win(pid)

        await self.workspace.eval_stack(i3)

    async def workspace_focus(self, i3, e):
        cur, prev = await self.find_workspace(e.current.name)

        if not cur:
            # getting rect
            for o in await i3.get_workspaces():
                if o.name == e.current.name:
                    cur = await self.get_workspace(e.current.name, o.rect)

        if prev:
            prev.next = cur.next
            cur.next = self.workspace
            self.workspace = cur

        await self.workspace.eval_stack(i3)

    async def get_workspace(self, name, rect):
        cur, prev = await self.find_workspace(name)

        if cur:
            return cur

        if prev == None:
            self.workspace = Workspace(name, rect)
            return self.workspace

        prev.next = Workspace(name, rect)
        return prev.next

    async def find_workspace(self, name):
        cur = self.workspace
        prev = None

        while cur != None:
            if cur.name == name:
                return (cur, prev)
            prev = cur 
            cur = cur.next

        return (cur, prev)


if __name__ == "__main__":
    c = Citsfsip()
    animid = 0
    asyncio.run(c.setup())

