# encoding: utf-8
from __future__ import division, print_function

import objc
from os.path import dirname, join
from GlyphsApp import Glyphs, UPDATEINTERFACE, GSNode, CURVE, OFFCURVE, LINE, GSPath
from GlyphsApp.plugins import GSBackgroundImage, SelectTool

from AppKit import NSBezierPath, NSBitmapImageRep, NSColor, \
    NSDeviceWhiteColorSpace, NSDeviceRGBColorSpace, NSGraphicsContext, \
    NSImageColorSyncProfileData, NSImageInterpolationNone, NSMakeRect, \
    NSPNGFileType, NSPoint, NSRoundLineCapStyle


plugin_id = "de.kutilek.scrawl"
default_pen_size = 2
default_pixel_size = 2
default_pixel_ratio = 1

# add code here
import os
import subprocess
from AppKit import NSImage, NSBMPFileType

def convertPath():
    layer = Glyphs.font.selectedLayers[0]
    d=layer.userData["de.kutilek.scrawl.data"]
    nsi = NSImage.alloc().initWithData_(d)
    print(nsi.representations()[0])
    data = (nsi.representations()[0]).representationUsingType_properties_(NSBMPFileType,None)
    data.writeToFile_atomically_("/tmp/foo.bmp",False)
    subprocess.call(["/usr/local/bin/potrace", "-s", "--flat", '-O', '5', "/tmp/foo.bmp"])
    import re
    with open("/tmp/foo.svg") as x: svg = x.read()
    path = re.search('path d="(.*)"', svg, re.DOTALL).group(1)
    lastcommand = ""
    nodes = []

    factor = 0.15

    def handleCurve(rs, nodes,cursorx, cursory):
      x1, y1 = (cursorx+int(rs.group(1))), (cursory+int(rs.group(2)))
      nodes.append(GSNode((x1*factor,y1*factor),OFFCURVE))
      x2, y2 = (cursorx+int(rs.group(3))), (cursory+int(rs.group(4)))
      nodes.append(GSNode((x2*factor,y2*factor),OFFCURVE))
      x, y = (cursorx+int(rs.group(5))), (cursory+int(rs.group(6)))
      nodes.append(GSNode((x*factor,y*factor),CURVE))
      cursorx, cursory = x,y
      return cursorx, cursory

    def handleLine(rs, nodes,cursorx, cursory):
      x1, y1 = (cursorx+int(rs.group(1))), (cursory+int(rs.group(2)))
      nodes.append(GSNode((x1*factor,y1*factor),LINE))
      cursorx, cursory = x1,y1
      return cursorx, cursory

    while len(path) > 0:
      rs = re.match('M\s*(\d+) (\d+)\s*',path)
      if rs:
        cursorx, cursory = int(rs.group(1)), int(rs.group(2))
        nodes.append(GSNode((cursorx*factor,cursory*factor),CURVE))
        path = path[rs.end():]
        continue

      rs = re.match('m\s*(-?\d+) (-?\d+)\s*',path)
      if rs:
        cursorx, cursory = cursorx+int(rs.group(1)), cursory+int(rs.group(2))
        nodes.append(GSNode((cursorx*factor,cursory*factor),CURVE))
        path = path[rs.end():]
        continue

      rs = re.match('c\s*(-?\d+)\s(-?\d+)\s(-?\d+)\s(-?\d+)\s(-?\d+)\s(-?\d+)\s*',path)
      if rs:
        cursorx, cursory = handleCurve(rs, nodes, cursorx, cursory)
        path = path[rs.end():]
        lastcommand = "c"
        continue

      rs = re.match('l\s*(-?\d+)\s(-?\d+)\s*',path)
      if rs:
        cursorx, cursory = handleLine(rs, nodes, cursorx, cursory)
        path = path[rs.end():]
        lastcommand = "l"
        continue

      rs = re.match('(-?\d+)\s(-?\d+)\s(-?\d+)\s(-?\d+)\s(-?\d+)\s(-?\d+)\s*',path)
      if rs and lastcommand == "c":
        cursorx, cursory = handleCurve(rs, nodes, cursorx, cursory)
        path = path[rs.end():]
        lastcommand = "c"
        continue

      rs = re.match('(-?\d+)\s(-?\d+)\s*',path)
      if rs and lastcommand == "l":
        cursorx, cursory = handleLine(rs, nodes, cursorx, cursory)
        path = path[rs.end():]
        continue

      rs = re.match('z\s*',path)
      if rs:
        # Flush nodes
        print(nodes)
        p = GSPath()
        p.nodes = nodes
        layer.paths.append(p)
        layer.cleanUpPaths()
        nodes = []
        path = path[rs.end():]
        continue

      raise ValueError("Couldn't parse "+path)

def initImage(layer, width, height, pixel_size=default_pixel_size, ratio=1):
    # See https://developer.apple.com/documentation/appkit/nsbitmapimagerep/1395538-init
    img = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bitmapFormat_bytesPerRow_bitsPerPixel_(
        None,    # BitmapDataPlanes
        int(round(width / pixel_size)),   # pixelsWide
        int(round(height / pixel_size / ratio)),  # pixelsHigh
        8,       # bitsPerSample: 1, 2, 4, 8, 12, or 16
        1,       # samplesPerPixel: 1 - 5
        False,   # hasAlpha
        False,   # isPlanar
        NSDeviceWhiteColorSpace,  # colorSpaceName
        # NSDeviceRGBColorSpace,
        0,       # bitmapFormat
        0,       # bytesPerRow
        0,       # bitsPerPixel
    )
    """
        NSCalibratedWhiteColorSpace
        NSCalibratedBlackColorSpace
        NSCalibratedRGBColorSpace
        NSDeviceWhiteColorSpace
        NSDeviceBlackColorSpace
        NSDeviceRGBColorSpace
        NSDeviceCMYKColorSpace
        NSNamedColorSpace
        NSCustomColorSpace
    """
    # The image is filled black for some reason, make it white
    current = NSGraphicsContext.currentContext()
    context = NSGraphicsContext.graphicsContextWithBitmapImageRep_(img)
    NSGraphicsContext.setCurrentContext_(context)
    NSColor.whiteColor().set()
    # NSBezierPath.setLineWidth_(1)
    NSBezierPath.fillRect_(NSMakeRect(0, 0, width, int(round(height / ratio))))
    NSGraphicsContext.setCurrentContext_(current)
    return img


class ScrawlTool(SelectTool):

    def settings(self):
        from vanilla import Group, Slider, TextBox, Window
        self.name = 'Scrawl'
        self.slider_value = 1  # current slider value

        # Create Vanilla window and group with controls
        viewWidth = 266
        viewHeight = 42
        self.sliderMenuView = Window((viewWidth, viewHeight))
        self.sliderMenuView.group = Group((0, 0, viewWidth, viewHeight))
        self.w = self.sliderMenuView.group
        y = 0
        self.w.text = TextBox((20, y, -20, 17), "%s Pen Size" % self.name)
        y += 18
        self.w.pen_size = Slider(
            (20, y, -60, 24),
            minValue=1,
            maxValue=256,
            value=float(self.slider_value),
            tickMarkCount=0,
            # stopOnTickMarks = False,
            # continuuous = True,
            callback=self.slider_callback,
            sizeStyle="small",
        )
        self.w.pen_size_text = TextBox((-50, y + 3, -20, 17), "%s" % default_pen_size)

        self.generalContextMenus = [
            {
                "view": self.sliderMenuView.group.getNSView()
            },
            {
                "name": Glyphs.localize({
                    'en': u'Delete Scrawl',
                    'de': u'Gekritzel löschen'
                }),
                "action": self.delete_data
            },
            {
                "name": Glyphs.localize({
                    'en': u'Save Scrawl To Background Image',
                    'de': u'Gekritzel als Hintergrundbild speichern'
                }),
                "action": self.save_background
            },
            # {
            #     "name": Glyphs.localize({
            #         'en': u'Save current size as master default',
            #         'de': u'Aktuelle Größe als Master-Standard speichern'
            #     }),
            #     "action": self.save_background
            # },
        ]
        self.keyboardShortcut = 'c'
        self.pen_size = default_pen_size
        self.pixel_size = default_pixel_size
        self.pixel_ratio = default_pixel_ratio
        self.rect = NSMakeRect(0, 0, 1000, 1000)
        self.data = None
        self.prev_location = None
        self.erase = False
        self.mouse_position = None
        self.layer = None
        self.needs_save = False
        self.current_layer = self.get_current_layer()

    def start(self):
        pass

    def get_current_layer(self):
        try:
            editView = self.editViewController().graphicView()
        except:
            return None
        return editView.activeLayer()

    def activate(self):
        self.current_layer = self.get_current_layer()
        if self.current_layer is not None:
            self.loadScrawl()
            self.w.pen_size.set(self.pen_size)
            self.w.pen_size_text.set(self.pen_size)
            self.prev_location = None
        Glyphs.addCallback(self.update, UPDATEINTERFACE)

    def deactivate(self):
        Glyphs.removeCallback(self.update)

    def foreground(self, layer):
        try:
            self.mouse_position = self.editViewController().graphicView().getActiveLocation_(Glyphs.currentEvent())
        except:
            # self.logToConsole("foreground: mouse_position: %s" % str(e))
            self.mouse_position = None
            return

        if self.mouse_position is not None:
            # Draw a preview circle at the mouse position
            x, y = self.mouse_position
            rect = NSMakeRect(
                x - self.pen_size / 2,
                y - self.pen_size * self.pixel_ratio / 2,
                self.pen_size,
                self.pen_size * self.pixel_ratio
            )
            path = NSBezierPath.bezierPathWithOvalInRect_(rect)
            path.setLineWidth_(1)
            if self.erase:
                NSColor.redColor().set()
            else:
                NSColor.lightGrayColor().set()
            path.stroke()

    def background(self, layer):
        self.layer = layer
        # draw pixels
        if self.data is None:
            return
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.currentContext().setImageInterpolation_(NSImageInterpolationNone)
        self.data.drawInRect_(self.rect)
        NSGraphicsContext.restoreGraphicsState()

    def keyDown_(self, event):
        if event.characters() == "d":
            # Delete the scrawl
            # FIXME: Doesn't work
            self.delete_data
        elif event.characters() == "e":
            # Toggle between draw and eraser mode
            self.erase = not(self.erase)
            self.prev_location = None
            self.updateView()
        elif event.characters() == "r":
            convertPath()
        elif event.characters() in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self.pen_size = int(event.characters()) * self.pixel_size
            self.w.pen_size.set(self.pen_size)
            self.w.pen_size_text.set(self.pen_size)
            self.updateView()
        else:
            objc.super(ScrawlTool, self).keyDown_(event)

    def setPixel(self, event, dragging=False):
        if self.data is None:
            return False
        try:
            editView = self.editViewController().graphicView()
        except:
            return False

        layer = editView.activeLayer()
        try:
            master = layer.parent.parent.masters[layer.layerId]
        except KeyError:
            return False
        if master is None:
            return False

        # Get location of click in font coordinates
        Loc = editView.getActiveLocation_(event)
        loc_pixel = (
            (Loc.x - self.rect.origin.x) / self.pixel_size,
            (Loc.y - self.rect.origin.y) / self.pixel_size / self.pixel_ratio
        )
        if self.prev_location != loc_pixel:
            x, y = loc_pixel
            current = NSGraphicsContext.currentContext()
            context = NSGraphicsContext.graphicsContextWithBitmapImageRep_(self.data)
            if context is None:
                self.prev_location = loc_pixel
                print("Could not get context in setPixel")
                return False
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.setCurrentContext_(context)
            if self.erase:
                NSColor.whiteColor().set()
            else:
                NSColor.blackColor().set()
            effective_size = self.pen_size / self.pixel_size
            if dragging and self.prev_location is not None:
                px, py = self.prev_location
                path = NSBezierPath.alloc().init()
                path.setLineCapStyle_(NSRoundLineCapStyle)
                path.setLineWidth_(effective_size)
                # path.strokeLineFromPoint_toPoint_(x, y, x + self.pen_size, y + self.pen_size)
                path.moveToPoint_((px, py))
                path.lineToPoint_((x, y))
                path.stroke()
                self.needs_save = True
            else:
                half = effective_size / 2
                rect = NSMakeRect(
                    x - half,
                    y - half,
                    effective_size,
                    effective_size
                )
                path = NSBezierPath.bezierPathWithOvalInRect_(rect)
                path.fill()
                self.needs_save = True
            # For rectangular pens:
            # NSBezierPath.fillRect_(rect)
            NSGraphicsContext.setCurrentContext_(current)
            NSGraphicsContext.restoreGraphicsState()
            self.prev_location = loc_pixel
        return True

    def mouseDown_(self, event):
        if event.clickCount() == 3:
            self.mouseTripleDown_(event)
            return
        if event.clickCount() == 2:
            self.mouseDoubleDown_(event)
            return
        if self.setPixel(event):
            self.updateView()

    def mouseDragged_(self, event):
        if self.setPixel(event, True):
            self.updateView()

    def mouseUp_(self, event):
        if self.setPixel(event):
            if self.needs_save:
                self.saveScrawl()
                self.updateView()

    def __file__(self):
        """Please leave this method unchanged"""
        return __file__

    def update(self, sender=None):
        cl = self.get_current_layer()
        if cl != self.current_layer:
            if self.needs_save:
                self.saveScrawl()
            self.current_layer = cl
            self.loadScrawl()
            self.w.pen_size.set(self.pen_size)
            self.w.pen_size_text.set(self.pen_size)
            self.prev_location = None
        self.updateView()

    def updateView(self):
        currentTabView = Glyphs.font.currentTab
        if currentTabView:
            currentTabView.graphicView().setNeedsDisplay_(True)

    def delete_data(self, sender=None):
        for layer in Glyphs.font.selectedLayers:
            self.deleteScrawl(layer)
        self.updateView()

    def save_background(self, sender=None):
        for layer in Glyphs.font.selectedLayers:
            self.saveScrawlToBackground(layer)

    def slider_callback(self, sender=None):
        if sender is not None:
            self.pen_size = int("%i" % sender.get())
            self.w.pen_size_text.set(self.pen_size)
            self.prev_location = None
            self.updateView()

    def loadDefaultRect(self):
        # Make the default drawing rect based on master and layer dimensions
        font = self.current_layer.parent.parent
        upm = font.upm
        pad = int(round(upm / 10))

        try:
            descender = font.masters[self.current_layer.layerId].descender
        except (AttributeError, KeyError):
            descender = int(round(-upm / 5))

        self.rect = NSMakeRect(
            -pad,
            descender - pad,
            2 * pad + self.current_layer.width,
            2 * pad + upm
        )

    def loadScrawl(self):
        if self.current_layer is None:
            return

        pen_size = self.current_layer.userData["%s.size" % plugin_id]
        if pen_size is not None:
            self.pen_size = pen_size  # scrawl pixels
            # Otherwise, keep the previous size

        self.pixel_size = self.current_layer.userData["%s.unit" % plugin_id]
        if self.pixel_size is None:
            self.pixel_size = default_pixel_size  # font units

        self.pixel_ratio = self.current_layer.master.customParameters['ScrawlPenRatio']
        if self.pixel_ratio is None:
            self.pixel_ratio = default_pixel_ratio
        else:
            self.pixel_ratio = float(self.pixel_ratio)

        # Drawing rect
        rect = self.current_layer.userData["%s.rect" % plugin_id]
        if rect is None:
            self.loadDefaultRect()
        else:
            self.rect = NSMakeRect(*rect)

        # Image data
        data = self.current_layer.userData["%s.data" % plugin_id]
        if data is None:
            self.data = initImage(
                self.current_layer,
                self.rect.size.width,
                self.rect.size.height,
                self.pixel_size,
                self.pixel_ratio
            )
        else:
            try:
                self.data = NSBitmapImageRep.alloc().initWithData_(data)
                self.data.setProperty_withValue_(
                    NSImageColorSyncProfileData,
                    None
                )
            except:
                print("Error in image data of layer %s" % self.current_layer)
                self.data = initImage(
                    self.current_layer,
                    self.rect.size.width,
                    self.rect.size.height,
                    self.pixel_size,
                    self.pixel_ratio
                )
        self.needs_save = False

    def saveScrawl(self):
        if self.current_layer is None:
            return
        self.current_layer.userData["%s.size" % plugin_id] = int(round(self.pen_size))
        self.current_layer.userData["%s.unit" % plugin_id] = int(round(self.pixel_size))
        if self.data is None:
            del self.current_layer.userData["%s.data" % plugin_id]
            del self.current_layer.userData["%s.rect" % plugin_id]
        else:
            self.current_layer.userData["%s.rect" % plugin_id] = (
                self.rect.origin.x,
                self.rect.origin.y,
                self.rect.size.width,
                self.rect.size.height
            )
            imgdata = self.data.representationUsingType_properties_(NSPNGFileType, None)
            # print("Saving PNG with %i bytes ..." % len(imgdata))
            # if len(imgdata) > 2**16:
            #     print("Glyphs Bug: Image is too big to save")
            #     # imgdata.writeToFile_atomically_(join(dirname(__file__), "test.png"), False)
            self.current_layer.userData["%s.data" % plugin_id] = imgdata
        self.needs_save = False

    def deleteScrawl(self, layer):
        if layer is None:
            return
        for key in ("data", "unit", "rect", "size"):
            full_key = "%s.%s" % (plugin_id, key)
            if layer.userData[full_key] is not None:
                del layer.userData[full_key]
        self.needs_save = False

    def saveScrawlToBackground(self, layer):
        font = layer.parent.parent
        if font.filepath is None:
            print("You must save the Glyphs file before a Scrawl background image can be added.")
            return
        data = layer.userData["%s.data" % plugin_id]
        pixel_size = layer.userData["%s.unit" % plugin_id]
        pixel_ratio = layer.master.customParameters['ScrawlPenRatio']
        if pixel_ratio is None:
            pixel_ratio = default_pixel_ratio
        else:
            pixel_ratio = float(pixel_ratio)
        rect = NSMakeRect(*layer.userData["%s.rect" % plugin_id])
        if data is not None:
            image_path = join(dirname(font.filepath), "%s-%s.png" % (
                layer.layerId,
                layer.parent.name
            ))
            try:
                imgdata = NSBitmapImageRep.alloc().initWithData_(data)
            except:
                print("Error saving the image file.")
                return
            pngdata = imgdata.representationUsingType_properties_(NSPNGFileType, None)
            pngdata.writeToFile_atomically_(image_path, False)
            layer.backgroundImage = GSBackgroundImage(image_path)
            layer.backgroundImage.position = NSPoint(
                rect.origin.x,
                rect.origin.y
            )
            layer.backgroundImage.scale = (float(pixel_size), float(pixel_size * pixel_ratio))
