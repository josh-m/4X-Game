import pyglet
from pyglet.window import key

import math
from copy import deepcopy

from definitions import DiagDir, Terrain, Feature
from constants import  (MAP_DISPLAY_WIDTH, WINDOW_HEIGHT, UI_PANEL_WIDTH,
                        DRAW_X, DRAW_Y, SCROLL_MARGIN, SCROLL_SPEED)
from util import isEven
import resources
from tilesprite import TileSprite


#amount of pixels
TILE_THRESHOLD_X = 54
TILE_THRESHOLD_Y = 72

class GameWindow(pyglet.window.Window):

    def __init__(self, map, *args, **kwargs):
        super(GameWindow, self).__init__(   MAP_DISPLAY_WIDTH+UI_PANEL_WIDTH,
                                            WINDOW_HEIGHT, *args, **kwargs)

        self.map = map
        self.turn = 1
        
        self.fps_display = pyglet.window.FPSDisplay(self)
        self._show_fps = True

        self.batch = pyglet.graphics.Batch()
        self.terrain_group = pyglet.graphics.OrderedGroup(0)
        self.feature_group = pyglet.graphics.OrderedGroup(1)
        self.ui_group = pyglet.graphics.OrderedGroup(2)

        self.draw_list = list()

        self.cam_pos = [0,0]
        self.centerCameraOnTile(self.map.start_tile)
        self.cam_dx = 0
        self.cam_dy = 0
        self.scroll_dir = DiagDir.NONE
        self.ul_idx = [0,0]

        #UI text
        self.turn_label = pyglet.text.Label('Turn: 1', font_name='Arial',
                                        font_size=24, x=MAP_DISPLAY_WIDTH+10,
                                        y=WINDOW_HEIGHT, anchor_x='left', anchor_y='top',
                                        color = (0,0,0,255))
                                        
        self.terrain_label = pyglet.text.Label('Terrain: None', font_name='Arial',
                                        font_size=16, x=MAP_DISPLAY_WIDTH+10,
                                        y=WINDOW_HEIGHT-40, anchor_x='left', anchor_y='top',
                                        color = (0,0,0,255))
                              
        self.selection_sprite = pyglet.sprite.Sprite(img = resources.selection_image,
                                                    batch=self.batch,
                                                    group=self.ui_group)
        self.selection_sprite.x = -5000
        self.selection_sprite.y = -5000



        pyglet.clock.schedule_interval(self.update, 1/45.0)

        #determine index of top right tile based on initial camera
        self.cam_idx = pixelPosToMapLoc(self.cam_pos)
        
        #push cam_idx up and left for seamless scrolling
        if self.cam_idx[0] > 1:
            self.cam_idx[0] -= 2

        if self.cam_idx[1] > 0:
            self.cam_idx[1] -=1


        #add to draw batch
        for i in range(self.cam_idx[0], min(self.cam_idx[0]+DRAW_X, len(map.columns))):
            self.addDrawColumn(i)

    def on_draw(self):
        self.clear()
        self.batch.draw()
        if self._show_fps:
            self.fps_display.draw()
        
        #UI sidebar placeholder
        
        pyglet.graphics.draw(
                4, pyglet.gl.GL_QUADS,
                ('v2f',
                    (MAP_DISPLAY_WIDTH,WINDOW_HEIGHT,
                    MAP_DISPLAY_WIDTH,0,
                    MAP_DISPLAY_WIDTH+UI_PANEL_WIDTH,0,
                    MAP_DISPLAY_WIDTH+UI_PANEL_WIDTH,WINDOW_HEIGHT
                    )))
        
        
        self.turn_label.draw()
        self.terrain_label.draw()
            
            
    def update(self, dt):
        if self.scroll_dir != DiagDir.NONE:
            self.scroll(self.scroll_dir)

    def on_key_press(self, symbol, modifiers):
        if symbol == key.GRAVE:
            self._show_fps = not self._show_fps
        elif symbol == key.SPACE:
            self.turn += 1
            self.turn_label.text = 'Turn: ' + str(self.turn)

    def on_mouse_press(self,x,y,button,modifiers):
        min_distance = 5000000
        min_pos = [0,0]
        distance = 0.0

        #debugging
        min_sprite = None

        #TODO: lower cost of minimizing distance
        for sprite in self.draw_list:
            distance = math.sqrt( (sprite.x - x)**2 + (sprite.y - y)**2)
            if distance < min_distance:
                min_distance = distance
                min_pos = [sprite.x, sprite.y]
                min_sprite = sprite
        
        self.selection_sprite.x = min_pos[0]
        self.selection_sprite.y = min_pos[1]
        
        #selected_idx = (int(min_sprite.x), int(min_sprite.y))
        self.selected_tile = self.map.tileAt(min_sprite.map_pos)
        
        #determine terrain and update label
        if self.selected_tile.terrain == Terrain.WATER:
            self.terrain_label.text = 'Terrain: Ocean'
        elif self.selected_tile.terrain == Terrain.GRASS:
            self.terrain_label.text = 'Terrain: Grassland'
        else:
            self.terrain_labe.text = 'Terrain: Unknown'
        
        print("Selected Tile INDEX:" + str(min_sprite.map_pos) +
                " pixel pos:" + str(min_sprite.x) +","+str(min_sprite.y))

        print("draw_list length:" + str(len(self.draw_list)))
        

    def on_mouse_motion(self,x,y,dx,dy):
        self.scroll_dir = determine_scroll_dir(x,y)

    def on_mouse_leave(self,x,y):
        self.scroll_dir = DiagDir.NONE

    def scroll(self, dir):
        dx=0
        dy=0

        if dir==DiagDir.LEFT or dir==DiagDir.UL or dir==DiagDir.DL:
            dx = -SCROLL_SPEED
        elif dir==DiagDir.RIGHT or dir==DiagDir.UR or dir==DiagDir.DR:
            dx = SCROLL_SPEED

        if dir==DiagDir.UP or dir==DiagDir.UL or dir==DiagDir.UR:
            dy = SCROLL_SPEED
        elif dir==DiagDir.DOWN or dir==DiagDir.DR or dir==DiagDir.DL:
            dy = -SCROLL_SPEED

        self.cam_pos[0] += dx
        self.cam_pos[1] -= dy
        self.cam_dx -= dx
        self.cam_dy -= dy

        for sprite in self.draw_list:
            sprite.x = sprite.pix_pos[0] - self.cam_pos[0]
            sprite.y = sprite.pix_pos[1] + self.cam_pos[1]
        

        self.selection_sprite.x -= dx
        self.selection_sprite.y -= dy

        
        #do columns need to be updated?
        if self.cam_dx > TILE_THRESHOLD_X:
            #print("shift left")
            self.cam_dx -= TILE_THRESHOLD_X

            self.removeDrawColumn(self.cam_idx[0]+DRAW_X-1)

            self.cam_idx[0]-=1
            self.addDrawColumn(self.cam_idx[0])

        elif self.cam_dx < -TILE_THRESHOLD_X:
            #print("shift right")
            self.cam_dx += TILE_THRESHOLD_X

            self.removeDrawColumn(self.cam_idx[0])
            self.cam_idx[0]+=1

            self.addDrawColumn(self.cam_idx[0]+DRAW_X-1)

        if self.cam_dy > TILE_THRESHOLD_Y:
            #print ("shift down")
            self.cam_dy -= TILE_THRESHOLD_Y

            self.removeDrawRow(self.cam_idx[1])
            self.cam_idx[1]+=1

            self.addDrawRow(self.cam_idx[1]+DRAW_Y-1)

        elif self.cam_dy < -TILE_THRESHOLD_Y:
            #print("shift up")
            self.cam_dy += TILE_THRESHOLD_Y
            self.removeDrawRow(self.cam_idx[1]+DRAW_Y-1)
            self.cam_idx[1]-=1
            self.addDrawRow(self.cam_idx[1])

    def addDrawRow(self, row_idx):
        map_row = self.map.row( row_idx,
                                start_col=self.cam_idx[0],
                                end_col=self.cam_idx[0]+DRAW_X)
        assert(len(map_row) >= DRAW_X)

        for tile in map_row:
            terr_sprite = TileSprite(   map_pos = tile.getMapPos(),
                                        img = tile.terr_img,
                                        batch = self.batch,
                                        group = self.terrain_group)
            pos = tile.getPixPos()
            terr_sprite.x = (pos[0] - self.cam_pos[0])
            terr_sprite.y = (pos[1] + self.cam_pos[1])

            self.draw_list.append(terr_sprite)

            if tile.feature != None:
                ftr_sprite = TileSprite( map_pos = tile.getMapPos(),
                                        img = tile.featureImg(),
                                        batch = self.batch,
                                        group = self.feature_group)
                pos = tile.getPixPos()
                ftr_sprite.x = pos[0] - self.cam_pos[0]
                ftr_sprite.y = pos[1] + self.cam_pos[1]
                if tile.feature == Feature.FOREST:
                    ftr_sprite.scale = 0.8
                self.draw_list.append(ftr_sprite)

    def removeDrawRow(self, row):
        #Remove sprites from right
        to_remove = list(filter(
                lambda x: isInRow(x, row), self.draw_list))
        #assert(len(to_remove) >= 10)

        for sprite in to_remove:
            self.draw_list.remove(sprite)
            sprite.delete() #immediately removes sprite from video memory

    def removeDrawColumn(self, col):
        to_remove = list(filter(
                lambda x: isInColumn(x, col), self.draw_list))
        #assert(len(to_remove) >= 10)

        for sprite in to_remove:
            self.draw_list.remove(sprite)
            sprite.delete() #immediately removes sprite from video memory

    def addDrawColumn(self, col_idx):
        map_col = self.map.column(  col_idx,
                                    start_row=self.cam_idx[1],
                                    end_row=self.cam_idx[1]+DRAW_Y)
        assert(len(map_col) >= DRAW_Y)

        for tile in map_col:
            terr_sprite = TileSprite(   map_pos = tile.getMapPos(),
                                        img = tile.terr_img,
                                        batch = self.batch,
                                        group = self.terrain_group)
            pos = tile.getPixPos()
            terr_sprite.x = (pos[0] - self.cam_pos[0])
            terr_sprite.y = (pos[1] + self.cam_pos[1])

            self.draw_list.append(terr_sprite)

            if tile.feature != None:
                ftr_sprite = TileSprite( map_pos = tile.getMapPos(),
                                        img = tile.featureImg(),
                                        batch = self.batch,
                                        group = self.feature_group)
                pos = tile.getPixPos()
                ftr_sprite.x = pos[0] - self.cam_pos[0]
                ftr_sprite.y = pos[1] + self.cam_pos[1]
                if tile.feature == Feature.FOREST:
                    ftr_sprite.scale = 0.8

                self.draw_list.append(ftr_sprite)

    def centerCameraOnSprite(self, sprite):
        pos = [0,0]
        pos = mapLocToPixelPos(sprite.map_pos)

        pos[0] -= MAP_DISPLAY_WIDTH/2
        pos[1] = -pos[1]
        #adjust for odd columns
        if not isEven(sprite.map_pos[0]):
            pos[1] += 36
        pos[1] += WINDOW_HEIGHT/2

        self.cam_pos = pos

    def centerCameraOnTile(self, tile):
        pos = [0,0]
        pos = tile.getPixPos()

        pos[0] -= MAP_DISPLAY_WIDTH/2
        pos[1] = -pos[1]
        #adjust for odd columns
        if not isEven(tile.pos[0]):
            pos[1] += 36
        pos[1] += WINDOW_HEIGHT/2

        self.cam_pos = pos

def isInRow(t_sprite, row):
    if t_sprite.map_pos[1] == row:
        return True
    else:
        return False

def isInColumn(t_sprite, column):
    #print("scol:"+str(t_sprite.map_pos[1])+" col:"+str(column))
    if t_sprite.map_pos[0] == column:
        return True
    else:
        return False



def determine_scroll_dir(mouse_x, mouse_y):
    scroll_dir = DiagDir.NONE
    
    if mouse_x > MAP_DISPLAY_WIDTH:
        return scroll_dir

    if mouse_x < SCROLL_MARGIN:
        if mouse_y < SCROLL_MARGIN:
            scroll_dir = DiagDir.DL
        elif mouse_y > WINDOW_HEIGHT - SCROLL_MARGIN:
            scroll_dir = DiagDir.UL
        else:
            scroll_dir = DiagDir.LEFT
    elif mouse_x > MAP_DISPLAY_WIDTH - SCROLL_MARGIN:
        if mouse_y < SCROLL_MARGIN:
            scroll_dir = DiagDir.DR
        elif mouse_y > WINDOW_HEIGHT - SCROLL_MARGIN:
            scroll_dir = DiagDir.UR
        else:
            scroll_dir = DiagDir.RIGHT
    elif mouse_y < SCROLL_MARGIN:
        scroll_dir = DiagDir.DOWN
    elif mouse_y > WINDOW_HEIGHT - SCROLL_MARGIN:
        scroll_dir = DiagDir.UP

    return scroll_dir

def whereOffscreen(sprite_x, sprite_y):
    off_dir = DiagDir.NONE
    OFF_MARGIN = 36

    if sprite_x < -OFF_MARGIN:
        if sprite_y < -OFF_MARGIN:
            off_dir = DiagDir.DL
        elif sprite_y > WINDOW_HEIGHT + OFF_MARGIN:
            off_dir = DiagDir.UL
        else:
            off_dir = DiagDir.LEFT
    elif sprite_x > MAP_DISPLAY_WIDTH + OFF_MARGIN:
        if sprite_y < -OFF_MARGIN:
            off_dir = DiagDir.DR
        elif sprite_y > WINDOW_HEIGHT + OFF_MARGIN:
            off_dir = DiagDir.UR
        else:
            off_dir = DiagDir.RIGHT
    elif sprite_y < -OFF_MARGIN:
        off_dir = DiagDir.DOWN
    elif sprite_y > WINDOW_HEIGHT + OFF_MARGIN:
        off_dir = DiagDir.UP

    return off_dir

def isOffscreen(sprite):
    if whereOffscreen(sprite.x, sprite.y) != DiagDir.NONE:
        return True
    else:
        return False

def pixelPosToMapLoc(pix_pos):
    x_offset = 54
    y_offset = 72
    y_margin = y_offset/2

    col_idx = (pix_pos[0] - 36) / x_offset

    row_idx = pix_pos[1]
    if isEven(col_idx):
        row_idx -= y_margin

    row_idx = row_idx / y_offset

    return [int(col_idx), int(row_idx)]


def mapLocToPixelPos(loc, relative = False):
    col_idx = loc[0]
    row_idx = loc[1]

    x_offset = 54
    y_offset = 72 #image size

    y_pos = WINDOW_HEIGHT - 36
    if isEven(col_idx):
        y_margin = y_offset/2
        y_pos = WINDOW_HEIGHT - 36 - y_margin

    x_pos = x_offset * (col_idx) + 36
    y_pos -= y_offset * (row_idx)

    if relative:
        return [x_pos - self.cam[0], y_pos - self.cam[1]]
    else:
        return [x_pos, y_pos]