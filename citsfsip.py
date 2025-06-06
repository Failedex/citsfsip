#! /usr/bin/env python3
from i3ipc import Rect, Event
from i3ipc.aio import Connection
import time
import math
import asyncio

FPS = 60 
DURATION = 0.6
try:
    import anims
    DX = anims.ease_out_bounce
except: 
    DX = lambda t: 1 - (1-t)*(1-t)

class Workspace():
    def __init__(self, name, rect):
        self.name = name
        self.stack = None
        self.count = 0
        self.screen = rect
        self.next = None
        self.ratio = 0.5

    async def find_window(self, id): 
        cur = self.stack 
        prev = None 
        while cur != None and cur.id != id:
            prev = cur 
            cur = cur.next
        
        return (cur, prev)

    async def add_win(self, id):
        new = Window(dict(
            x = 0, 
            y = 0, 
            width = 100, 
            height = 100
        ), id)

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
            if not tree.find_by_id(cur.id):
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
        aid = animid

        current = []
        cur = self.stack 
        tree = await i3.get_tree()
        while cur:
            win = tree.find_by_id(cur.id)
            if win == 0:
                return

            win.rect.y -= win.deco_rect.height
            win.rect.height += win.deco_rect.height
            current.append(win.rect)

            cur = cur.next

        start = time.time()
        frames = int(DURATION * FPS)

        for i in range(frames):
            fstart = time.time()
            t = (fstart-start)/DURATION
            dx = DX(t)

            if t >= 1:
                dx = 1

            cur = self.stack
            j = 0 
            while cur != None:
                if animid != aid:
                    return

                await cur.move(i3, current[j], dx)
                j += 1
                cur = cur.next

            if t >= 1:
                return

            # manual cap at 60hz
            await asyncio.sleep(max(1/FPS - (fstart-time.time()), 0))

class Window(Rect):
    def __init__(self, data, id):
        self.id = id
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

        await i3.command(f"[con_id={self.id}] resize set width {int(width)}px height {int(height)}px")
        await i3.command(f"[con_id={self.id}] move absolute position {int(x)}px {int(y)}px")

class Citsfsip:
    def __init__(self):
        self.i3 = None
        self.workspace = None
        
    async def setup(self):
        self.i3 = await Connection().connect()

        # await self.i3.command("bindsym Mod4+k mark '_up'")
        # await self.i3.command("bindsym Mod4+j mark '_down'")
        # await self.i3.command("bindsym Mod4+h mark '_incm'")
        # await self.i3.command("bindsym Mod4+l mark '_decm'")
        # await self.i3.command("bindsym Mod4+Shift+Return mark '_master'")

        tree = await self.i3.get_tree()

        for w in tree.workspaces():
            wo = await self.get_workspace(w.name, w.rect)
            
            for l in w.floating_nodes:
                await wo.add_win(l.id)

        self.i3.on(Event.WINDOW_NEW, self.window_new)
        self.i3.on(Event.WINDOW_CLOSE, self.window_close)
        self.i3.on(Event.WINDOW_MARK, self.window_mark)
        self.i3.on(Event.WINDOW_MOVE, self.window_move)
        self.i3.on(Event.WORKSPACE_FOCUS, self.workspace_focus)
        await self.i3.main()

    async def window_new(self, i3, e):
        cur = e.container
        await cur.command("floating enable")
        await self.workspace.add_win(cur.id)
        await self.workspace.eval_stack(i3)

    async def window_close(self, i3, e):
        await self.workspace.eval_stack(i3)

    async def window_mark(self, i3, e):
        stack = self.workspace.stack 
        marks = e.container.marks

        if len(marks) == 0 or not self.workspace:
            return
        await e.container.command("unmark")
        m = e.container

        if "_master" in marks:
            cur, prev = await self.workspace.find_window(m.id)

            if not cur or not prev:
                return 

            prev.next = cur.next
            cur.next = self.workspace.stack
            self.workspace.stack = cur

            await self.workspace.eval_stack(i3)
            return 

        if "_up" in marks:
            cur, prev = await self.workspace.find_window(m.id)

            if not prev:
                prev = cur 
                while prev.next != None:
                    prev = prev.next

            await i3.command(f"[con_id={prev.id}] focus")
            return

        if "_down" in marks:
            cur, _ = await self.workspace.find_window(m.id)

            front = cur.next 
            if not front:
                front = self.workspace.stack

            await i3.command(f"[con_id={front.id}] focus")
            return

        if "_incm" in marks:
            self.workspace.ratio -= 0.02
            await self.workspace.eval_stack(i3)
            return

        if "_decm" in marks:
            self.workspace.ratio += 0.02
            await self.workspace.eval_stack(i3)
            return

    async def window_move(self, i3, e):
        id = e.container.id or None
        if id == None:
            return

        cur = self.workspace.stack 
        prev = None
        while cur != None:
            if cur.id == id:
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
                if n.id == id:
                    ws = await self.get_workspace(w.name, w.rect)
                    await ws.add_win(id)

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

