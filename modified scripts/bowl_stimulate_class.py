import numpy as np
import matplotlib.pyplot as plt
from bowl import *
import time
import sys
import functools
import socket
import select
import mmap
import pandas as pd



class Stimulation_Pipeline():
    
    def __init__(self,img_size=(360, 720,3), fov_azi=(0,180), fov_ele=(15,140),img_offsetx=3840+3240,img_offsety=2400,name = "Arena"):
        #initialize Projection Objects
        azi_pix = int(img_size[1]/360*fov_azi[1])
        ele_pix = int(img_size[0]/180*fov_ele[1])
        
        self.azi_pix = azi_pix
        self.ele_pix = ele_pix
        
        self.xdim = img_size[1]
        self.ydim = img_size[0]
        self.resolution = np.array([1/(self.ele_pix/fov_ele[1]),1/(self.azi_pix/fov_azi[1])])
        self.image_size = img_size
        self.dest = np.zeros(img_size,dtype = "uint8")
        self.Stimulus = Stimulus(self.dest.shape)
        self.Projector_1 = Projector()
        self.Projector_1.initialize_projection_matrix((ele_pix,azi_pix),fov_azi,fov_ele)
        self.dt = 0
        self.time_start =0
        self.frames=0
        self.oldframe =0
        

        #initialize Window output

        self.WINDOW_NAME = name
        self.width_first  = img_offsetx
        self.height_first = img_offsety
        cv2.namedWindow(self.WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.moveWindow(self.WINDOW_NAME, self.width_first, self.height_first)
        cv2.setWindowProperty(self.WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        print("initialize Stimulation Pipeline < ",self.WINDOW_NAME," >: xdim=,",self.xdim,"ydim=",self.ydim,
              "at position x=", self.width_first,"y=", self.height_first)
        # generate stimulus texture 

    def generate_grating_vertical(self,color1, color2,spatial_freq):
        xdim=self.xdim
        ydim=self.ydim
        pixperdeg = int(xdim/360*spatial_freq)
        pic = np.ones([ydim,xdim],dtype = "uint8")*color1
        for x in range(int(xdim/(pixperdeg))):
            pic[:,2*x*pixperdeg:(2*x+1)*pixperdeg] = color2
        return pic

    def generate_grating_horizontal(self,color1, color2,spatial_freq):
        xdim=self.xdim
        ydim=self.ydim
        pixperdeg = int(xdim/360*spatial_freq)
        pic = np.ones([ydim,xdim],dtype = "uint8")*color1
        for y in range(int(ydim/(pixperdeg))):
            pic[2*y*pixperdeg:(2*y+1)*pixperdeg,:] = color2
        return pic


    def generate_grating_checkerboard(self,color1,spatial_freq):
        xdim=self.xdim
        ydim=self.ydim
        pixperdeg = int(xdim/360*spatial_freq)
        pic = np.zeros([ydim,xdim],dtype = "uint8")
        pic1 = np.zeros([ydim,xdim],dtype = "uint8")
        for x in range(int(xdim/(pixperdeg))):
            pic[:,2*x*pixperdeg:(2*x+1)*pixperdeg] = 1
        for y in range(int(ydim/(pixperdeg))):
            pic1[2*y*pixperdeg:(2*y+1)*pixperdeg,:] = 1
        pic = ((pic+pic1)%2)*color1
        return pic

    def generate_grating_sine_vertical(self,amplitude, offset,spatial_freq):
        xdim=self.xdim
        ydim=self.ydim
        f = int(360/spatial_freq)
        t = np.linspace(0,2*np.pi*f,xdim)
        val = amplitude*np.sin(t)+offset
        ys = np.ones(ydim)
        pic = np.outer(ys,val)
        return pic.astype("uint8")

    def generate_grating_sine_horizontal(self,amplitude, offset,spatial_freq):
        xdim=self.xdim
        ydim=self.ydim
        f = int(360/spatial_freq)
        t = np.linspace(0,2*np.pi*f,ydim)
        val = amplitude*np.sin(t)+offset
        ys = np.ones(xdim)
        pic = np.outer(val,ys)
        return pic.astype("uint8")

    def generate_bar_vertical(self, width, color, color_b, offset =0):
        xdim=self.xdim
        ydim=self.ydim
        width *= int(xdim/360)
        offset = int((xdim/2) + offset - (width/2))
        pic = np.ones([ydim,xdim],dtype = "int8")*color_b
        pic[:,offset:offset+width] = color
        return pic
        
    def generate_checker_vertical(self, pixel_size=5, width_in_pixels=3, color1=0, color2=254, color_b=100, offset=0):
        xdim=self.xdim
        ydim=self.ydim
        pixel_size *= int(xdim/360)
        squares_per_row, squares_per_col = int(width_in_pixels), int(ydim / pixel_size)
        pic = np.ones([ydim,xdim],dtype = "int8")*color_b  
        offset = int((xdim/2) + offset - (pixel_size*width_in_pixels/2))
        for i in range(squares_per_row):
            for j in range(squares_per_col):
                offsetx = (i * pixel_size) + offset
                offsety = (j * pixel_size)
                pic[offsety : offsety + pixel_size, offsetx : offsetx + pixel_size] = np.random.choice([color1, color2])

        return pic

    def generate_colored_screen(self, color):
        xdim=self.xdim
        ydim=self.ydim
        pic = np.ones([ydim,xdim],dtype = "uint8")*color
        return pic

    def generate_checker_screen(self, pixel_size, color1, color2):
        xdim=self.xdim
        ydim=self.ydim
        pixel_size *= int(xdim/360)
        squares_per_row, squares_per_col = int(xdim/pixel_size), int(ydim / pixel_size)
        pic = np.ones([ydim,xdim],dtype = "int8")
        for i in range(squares_per_row):
            for j in range(squares_per_col):
                offsetx = (i * pixel_size)
                offsety = (j * pixel_size)
                pic[offsety : offsety + pixel_size, offsetx : offsetx + pixel_size] = np.random.choice([color1, color2])

        return pic

    def generate_edge_vertical(self,color1, color2):
        xdim=self.xdim
        ydim=self.ydim
        pic = np.ones([ydim,xdim],dtype = "uint8")*color1
        pic[:,:int(xdim/2)]= color2
        return pic


    def show_dark_screen(self,duration):
        output2 = np.zeros((self.Projector_1.resolution[1], self.Projector_1.resolution[0],3),dtype = "uint8")
        cv2.imshow(self.WINDOW_NAME,output2)
        key = cv2.waitKey(int(duration*1000))


    def show_trigger(self):
        output2 = np.zeros((self.Projector_1.resolution[1], self.Projector_1.resolution[0],3),dtype = "uint8")
        output2[-45:-5,-45:-5] = 128
        cv2.imshow(self.WINDOW_NAME,output2)
        key = cv2.waitKey(30)

    #rotational execution

    def generate_fictracRotationalPipe(self, texture, inverted, MMapName, gain, duration, roll=0, pitch=0, rot_offset=(0,0,0)):

        self.show_trigger()
        self.show_dark_screen(0.1)
        fpss = np.array([])
        dts = np.array([])
        fps = 0
        timer = cv2.getTickCount()

        Input_im = texture
        resized = cv2.cvtColor(Input_im, cv2.COLOR_GRAY2RGB)
        self.show_dark_screen(0.1)
        self.show_trigger()
        self.time_start = time.time()
        
        while (duration == -1.00) | (time.time() < self.time_start + duration):
            self.dt = time.time()-self.time_start
            shiftY = -2000
            InBetweenFrameMS = 1

            try:
                with mmap.mmap(-1, 1024, MMapName) as mm:
                    line = mm.readline().decode().strip()
                    toks = line.split(", ")
                    
                    # Check that we have sensible tokens
                    if ((len(toks) > 24) & (toks[0] == "FT")):
                        # Extract FicTrac variables
                        # (see https://github.com/rjdmoore/fictrac/blob/master/doc/data_header.txt for descriptions)
                        cnt = int(toks[1])
                        dr_cam = [float(toks[2]), float(toks[3]), float(toks[4])]
                        #err = float(toks[5])
                        #dr_lab = [float(toks[6]), float(toks[7]), float(toks[8])]
                        #r_cam = [float(toks[9]), float(toks[10]), float(toks[11])]
                        #r_lab = [float(toks[12]), float(toks[13]), float(toks[14])]
                        #posx = float(toks[15])
                        #posy = float(toks[16])
                        #heading = float(toks[17])
                        #step_dir = float(toks[18])
                        #step_mag = float(toks[19])
                        #intx = float(toks[20])
                        #inty = float(toks[21])
                        #ts = float(toks[22])
                        #seq = int(toks[23])
                        shiftY = dr_cam[1]
                
            except Exception as e:
                print(f"Error: {str(e)}")

            if (shiftY == -2000):
                print(MMapName + " is not connected")
                InBetweenFrameMS = 1000

            shiftY *= gain

            rotated = self.Stimulus.rot_equi_img(resized,self.dest,roll*shiftY,pitch*shiftY,shiftY)
            rotated = self.Stimulus.rot_equi_img(rotated,self.dest,rot_offset[0],rot_offset[1],rot_offset[2])
            croped = select_fov(rotated)
            masked = self.Projector_1.project_image(croped)
            output = self.Projector_1.mask_image(masked)
            if inverted:
                output = cv2.rotate(output, cv2.ROTATE_180)
            cv2.imshow(self.WINDOW_NAME,output)

            tick = cv2.getTickCount()-timer
            fps = cv2.getTickFrequency()/(tick)
            timer = cv2.getTickCount()

            if (InBetweenFrameMS == 1):
                fpss = np.append(fpss,fps)
                dts = np.append(dts,self.dt)

            key = cv2.waitKey(InBetweenFrameMS)
            if key == 27:#if ESC is pressed, exit loop
                cv2.destroyAllWindows()
                break
            
        self.show_trigger()
        self.show_dark_screen(0.1)
        if(len(fpss) != 0):
            print("mean fps" + str(np.mean(fpss)))
        else:
            print("no closed loop fps recorded")

    def generateLoop(self, arena, objects_and_backgrounds, bouncing_limits, side_duration, side_per_phase, break_duration, iteration=1, framerate=60, inverted=False, rot_offset=(0,0,0)):

        self.arena = arena
        self.show_trigger()
        self.show_dark_screen(0.1)
        fpss = np.array([])
        fps = 0
        timer = cv2.getTickCount()
        self.show_dark_screen(0.1)
        self.show_trigger()
        self.time_start = time.time()
                
        self.arena.frames=0
        print("video framerate =",framerate)
        self.framerate = framerate

        xdim = self.arena.xdim
        ydim = self.arena.ydim
        bouncing_limits = bouncing_limits*(xdim/360)
        phase_number = len(objects_and_backgrounds)
        Abs_side_start = 0.0
        Abs_phase_start = 0.0
        Abs_loop_start = 0.0
        current_phase = 0
        current_side = 0
        current_loop = 0
        new_phase = True
        new_side = True
        new_loop = True
        in_break = True
        
        object = 0
        background = 0

        log = []
       
        while current_loop <= iteration:
            theoretical_elapsed_time = self.arena.frames*(1/self.framerate)
            self.arena.dt = time.time()-self.arena.time_start
            now = time.time()
            pic = self.arena.oldframe
            
            if (self.arena.dt > theoretical_elapsed_time) | isinstance(self.arena.oldframe, int):    
                self.arena.frames += 1

                if new_loop:
                    Abs_loop_start = now
                    current_phase = 0
                    new_phase = True
                    new_loop = False
                
                if new_phase:
                    Abs_phase_start = now
                    new_scene = objects_and_backgrounds[current_phase]()
                    object = new_scene[0]
                    background = new_scene[1]
                    current_side = 0
                    new_phase = False
                    
                phase_elapsed_time = now - Abs_phase_start - break_duration
                loop_elapsed_time = now - Abs_loop_start
                
                if phase_elapsed_time < 0:
                    in_break = True
                    pic = np.zeros([xdim, ydim],dtype = "uint8")

                else:
                    if in_break:
                        new_side = True
                        in_break = False
                    
                    if new_side:
                        Abs_side_start = now
                        new_side = False
                    
                    side_elpased_time = now - Abs_side_start
                        
                    if side_elpased_time >= side_duration:
                        log.append(("side", current_side, Abs_side_start, now, now-Abs_side_start))
                        new_side = True
                        current_side += 1
                    
                    if current_side == side_per_phase:
                        log.append(("phase", current_phase, Abs_phase_start, now, now-Abs_phase_start))
                        new_phase = True
                        current_phase += 1
                    
                    if current_phase >= phase_number:
                        log.append(("loop", current_loop, Abs_loop_start, now, now-Abs_loop_start ))
                        new_loop = True
                        current_loop += 1
                        
                    if (not new_phase) & (not new_side) & (not new_loop):
                        is_side_even = - 1 + (current_side%2 != 0)*2
                        starting_pos = 1 - is_side_even*bouncing_limits/2
                        progress = 1-(side_duration - side_elpased_time)/side_duration
                        shift = starting_pos + progress*bouncing_limits*is_side_even
                        new_indices = (np.arange(xdim) - int(shift)) % xdim
                        pic = object
                        pic = pic[:, new_indices]
                        mask = pic == -1
                        pic[mask] = background[mask]
                    
            resized = cv2.cvtColor(pic.astype(np.uint8), cv2.COLOR_GRAY2RGB)
            self.arena.oldframe = pic
            
            if (rot_offset == (0,0,0)):
                rotated = resized
            else:
                rotated = self.Stimulus.rot_equi_img(resized,self.dest,rot_offset[0],rot_offset[1],rot_offset[2])
                
            croped = select_fov(rotated)
            masked = self.Projector_1.project_image(croped)
            output = self.Projector_1.mask_image(masked)
            if inverted:
                output = cv2.rotate(output, cv2.ROTATE_180)
            cv2.imshow(self.WINDOW_NAME,output)
            tick = cv2.getTickCount()-timer
            fps = cv2.getTickFrequency()/(tick)
            timer = cv2.getTickCount()
            fpss = np.append(fpss,fps)
            key = cv2.waitKey(1)#pauses for 1ms seconds before fetching next image
            if key == 27:#if ESC is pressed, exit loop
                cv2.destroyAllWindows()
                break

        self.show_trigger()
        self.show_dark_screen(0.1)
        print ("mean fps " + str(np.mean(fpss)))
        df = pd.DataFrame(log, columns=["Event", "ID", "AbsoluteStart", "AbsoluteEnd", "Duration"])
        return df

    
    
    def generate_rotational(self,texture,duration,roll=0,pitch=0,yaw=0,rot_offset=(0,30,0)):
        
        # the "generate_rotational" function creates a start time and manages runtime and timing it  uses an pre generated texture to project it onto the projector.
        # the pre generated texture can be rotated online in constant speed along every rotational axis.

        self.show_trigger()
        self.show_dark_screen(0.1)
        fpss = np.array([])
        dts = np.array([])
        fps = 0
        timer = cv2.getTickCount()

        Input_im = texture
        resized = cv2.cvtColor(Input_im, cv2.COLOR_GRAY2RGB)
        self.show_dark_screen(0.1)
        self.show_trigger()
        self.time_start = time.time()
        i=0
        while time.time() < self.time_start + duration:
            
            self.dt = time.time()-self.time_start
            rotated = self.Stimulus.rot_equi_img(resized,self.dest,roll*self.dt,pitch*self.dt,yaw*self.dt)
            rotated = self.Stimulus.rot_equi_img(rotated,self.dest,rot_offset[0],rot_offset[1],rot_offset[2])
            croped = select_fov(rotated)
            masked = self.Projector_1.project_image(croped)
            output = self.Projector_1.mask_image(masked)
            cv2.imshow(self.WINDOW_NAME,output)

            tick = cv2.getTickCount()-timer
            fps = cv2.getTickFrequency()/(tick)
            timer = cv2.getTickCount()
            fpss = np.append(fpss,fps)
            dts = np.append(dts,self.dt)

            key = cv2.waitKey(1)#pauses for 1ms seconds before fetching next image

            if key == 27:#if ESC is pressed, exit loop
                cv2.destroyAllWindows()
                break
        self.show_trigger()
        self.show_dark_screen(0.1)
        print (np.mean(fpss))
        #print ((dts))
        #plt.plot(dts)
        #linear = np.linspace(0,duration,len(dts))
        #plt.plot(linear,dts-linear)
     
        
    def generate(self,function,duration=0,rot_offset=(0,0,0),*args, **kwargs):
        
        # the "generate" function creates a start time and manages runtime and timing it  uses an online generated texture to project it onto the projector.
        # function is an input function or object, which generates online textures, which are then projected.
        # once generate is called in the main loop the insered function/or object is initialized. Afterwards the Code in the generate function is executed
        # in the While loop, the function is called and args and kwargs are transfered.
        
        self.show_trigger()
        self.show_dark_screen(0.1)
        fpss = np.array([])
        fps = 0
        timer = cv2.getTickCount()
        self.show_dark_screen(0.1)
        self.show_trigger()
        self.time_start = time.time()
        
        while time.time() < self.time_start + duration:
            Input_im = function(*args, **kwargs)
            
            if(len(Input_im.shape)<3):
                resized = cv2.cvtColor(Input_im, cv2.COLOR_GRAY2RGB)
            else:
                resized = Input_im
            if (rot_offset == (0,0,0)):
                rotated = resized
            else:
                rotated = self.Stimulus.rot_equi_img(resized,self.dest,rot_offset[0],rot_offset[1],rot_offset[2])
                
            croped = select_fov(rotated)
            masked = self.Projector_1.project_image(croped)
            output = self.Projector_1.mask_image(masked)
            cv2.imshow(self.WINDOW_NAME,output)
            tick = cv2.getTickCount()-timer
            fps = cv2.getTickFrequency()/(tick)
            timer = cv2.getTickCount()
            fpss = np.append(fpss,fps)
            key = cv2.waitKey(1)#pauses for 1ms seconds before fetching next image
            if key == 27:#if ESC is pressed, exit loop
                cv2.destroyAllWindows()
                break
        self.show_trigger()
        self.show_dark_screen(0.1)
        print (np.mean(fpss))
        
        
    def looming_disk(self,radius,speed,distance,color_disc,color_bg,center=None):
        
        xdim=self.xdim
        ydim=self.ydim
        fac= int(ydim/180)
        if center is None: # use the middle of the image
            center = (int(xdim/2), int(ydim/2))
        else:
            center= np.asarray(center)
            center = center*fac
            
        self.dt = time.time()-self.time_start
        position = distance-(speed*self.dt)
        
        alpha = np.arctan((radius/position))
        pixel_radius = np.rad2deg(alpha)*fac
        
        Y, X = np.ogrid[:ydim, :xdim]
        dist_from_center = np.sqrt((X - center[0])**2 + (Y-center[1])**2)

        mask = dist_from_center <= pixel_radius
        pic = np.ones([ydim,xdim],dtype = "uint8")*color_bg
        pic[mask]=color_disc
        return pic
    

# each online calculated texture class consists of an initialization and an run function.
# this is necessary to initialize the stimulus parameters before runtime loop
# each online texture class is designed to get called by the Stimulation_Pipeline.generate() function

class ShowVideo():
    
    def __init__(self,arena,path,framerate=0,duration=0):
         
    
        self.arena = arena # object of the class Stimulation_Pipeline() 
        # This step is necessary in order to use functions and variables, such as time, from the stimulation pipeline class 
        # and to generate a separate initialisation function and a run function independently for each stimulus.
        
        self.video = cv2.VideoCapture(path)
        if framerate == 0:
            framerate = self.video.get(cv2.CAP_PROP_FPS)   
        frame_count = int(self.video.get(cv2.CAP_PROP_FRAME_COUNT))
        print("frame count =",frame_count)
        if duration==0:
            duration = frame_count/framerate
        elif duration > frame_count/framerate:
            print("video file to short")
            duration = frame_count/framerate
        
        print("videoduration =",duration)
        self.arena.frames=0
        print("video framerate =",framerate)
        self.framerate = framerate
        fpss = np.array([])
        fps = 0
        timer = cv2.getTickCount()

    
  
    def run(self,):
                        
        theoretical_elapsed_time = self.arena.frames*(1/self.framerate)
        self.arena.dt = time.time()-self.arena.time_start 
        #print("dt = ",self.arena.dt,"  frames = ",self.arena.frames)
        
        if self.arena.dt>=theoretical_elapsed_time:
            
            ok, frame = self.video.read()#first frame ? 
            self.arena.frames += 1
            if not ok:
                print('Cannot read video file.')

        else:
            frame = self.arena.oldframe
        resized = cv2.resize(frame,self.arena.image_size[0:2], interpolation = cv2.INTER_AREA)
        self.arena.oldframe = frame
        return resized
    
    
class LoomingDisk(): 
    
    def __init__(self,arena,center=None):
        self.arena = arena
        xdim=self.arena.xdim
        ydim=self.arena.ydim
        self.fac= int(ydim/180)
        if center is None: # use the middle of the image
            center = (int(xdim/2), int(ydim/2))
        else:
            self.center= np.asarray(center)
            self.center = self.center*self.fac
        self.pic = np.ones([ydim,xdim],dtype = "uint8")
        
    
    def run(self,radius,speed,distance,color_disc,color_bg):
        
     
        self.arena.dt = time.time()-self.arena.time_start
        position = distance-(speed*self.arena.dt)
        alpha = np.arctan((radius/position))
        pixel_radius = np.rad2deg(alpha)*self.fac
        Y, X = np.ogrid[:self.arena.ydim, :self.arena.xdim]
        dist_from_center = np.sqrt((X - self.center[0])**2 + (Y-self.center[1])**2)

        mask = dist_from_center <= pixel_radius
        self.pic = self.pic*color_bg
        self.pic[mask]=color_disc
        return self.pic
    

    
class ShowNoise():
    
    def __init__(self,arena,pixelsize,framerate=30):
         
    
        self.arena = arena # object of the class Stimulation_Pipeline() 
        # This step is necessary in order to use functions and variables, such as time, from the stimulation pipeline class 
        # and to generate a separate initialisation function and a run function independently for each stimulus.
        xdim=self.arena.xdim
        ydim=self.arena.ydim
        self.pic = np.zeros([ydim,xdim,3],dtype = "uint8")
        self.y_noise = self.arena.ele_pix*self.arena.resolution[0]/pixelsize
        self.x_noise = self.arena.azi_pix*self.arena.resolution[1]/pixelsize
        self.arena.frames=0
        print("video framerate =",framerate)
        self.framerate = framerate
        fpss = np.array([])
        fps = 0
        print("y noise pixel = ",self.y_noise, " x noise pixel = ",self.x_noise)
        np.random.seed(0)
        timer = cv2.getTickCount()
        

        
    def run(self):
                        
        theoretical_elapsed_time = self.arena.frames*(1/self.framerate)
        self.arena.dt = time.time()-self.arena.time_start 
        #print("dt = ",self.arena.dt,"  frames = ",self.arena.frames)
        
        if self.arena.dt>=theoretical_elapsed_time:

            Input_im = (np.random.randint(0,2,(int(self.y_noise ),int(self.x_noise),1))*255).astype("uint8")
            image = cv2.cvtColor(Input_im, cv2.COLOR_GRAY2RGB)    
            resized = cv2.resize(image,dsize=(self.arena.azi_pix, self.arena.ele_pix), interpolation = cv2.INTER_AREA)
            self.pic[0:280,180:540,:]= resized
 
            self.arena.frames += 1
        else:
            self.pic = self.arena.oldframe
            
        self.arena.oldframe = self.pic
        
        return self.pic
    

class ShowVerticalEdge():
    
    def __init__(self,arena):
         
    
        self.arena = arena # object of the class Stimulation_Pipeline() 
        # This step is necessary in order to use functions and variables, such as time, from the stimulation pipeline class 
        # and to generate a separate initialisation function and a run function independently for each stimulus.
        xdim=self.arena.xdim
        ydim=self.arena.ydim
        self.pic = np.zeros([ydim,xdim,3],dtype = "uint8")
        
        fpss = np.array([])
        fps = 0
        
        timer = cv2.getTickCount()
        

        
    def run(self,start,speed,color1,color2):
                        
        
        self.arena.dt = time.time()-self.arena.time_start 
        pixel_start = start/self.arena.resolution[1]
        pixel_shifted = (start+self.arena.dt*speed)/self.arena.resolution[1]
        pic = np.ones([self.arena.ydim,self.arena.xdim],dtype = "uint8")*color1
        pic[:,int(pixel_start):int(pixel_shifted)]=color2
        self.pic = cv2.cvtColor(pic, cv2.COLOR_GRAY2RGB)    
        
        return self.pic
