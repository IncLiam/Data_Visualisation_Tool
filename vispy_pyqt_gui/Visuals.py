import aioprocessing
from matplotlib.pyplot import cm
import numpy as np
from vispy.util.transforms import ortho
import vispy.app
from vispy import color
from vispy import gloo
import pyqtgraph as pg
import time


# Class for Pyqtgraph plot for single sensor output
class PyqtgraphPlotSensor:

    def __init__(self, *args):

        self.args = args
        self.Data_queue = args[0]
        self.selected_sensor = args[1]
        self.new_data = 0.
        self.in_graph_event = aioprocessing.AioEvent()

        self.graphWidget = pg.GraphicsLayoutWidget()
        self.graphWidget.setBackground('w')
        self.p1 = self.graphWidget.addPlot()

        pen = pg.mkPen(color=(255, 165, 0), width=4)

        # single pressure
        self.data1 = np.random.uniform(0, 0, size=100)
        self.curve1 = self.p1.plot(self.data1, pen=pen)
        self.p1.setYRange(0, 0.8, padding=0)
        self.p1.setTitle("Single Pressure Sensor Airflow Detection")
        self.p1.hideAxis('bottom')
        self.p1.hideAxis('left')

        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(50)

    def update1(self):
        self.data1[:-1] = self.data1[1:]  # shift data in the array one sample left
        self.data1[-1] = self.new_data
        self.curve1.setData(self.data1)

    # update all plots
    def update(self):
        if not self.Data_queue.empty():
            self.q_data = self.Data_queue.get_nowait()
            # TODO create function to get sensor from int argument
            self.new_data = self.q_data[3, 1]
            # print(self.q_data)
            # print(self.new_data)
        self.update1()


# Class for Vispy Heat Map for sensors output
class CanvasSensors(vispy.app.Canvas):

    def __init__(self, *args):
        self.in_heatmap_event = aioprocessing.AioEvent()

        # Image to be displayed
        self.W, self.H = 8, 4
        self.I = np.random.uniform(0, 1, (self.W, self.H)).astype(np.float32)
        colors = color.get_colormap("jet").map(self.I).reshape(self.I.shape + (-1,))

        # A simple texture quad
        self.data = np.zeros(4, dtype=[('a_position', np.float32, 2),
                                       ('a_texcoord', np.float32, 2)])

        self.data['a_position'] = np.array([[0, 0], [self.W, 0], [0, self.H], [self.W, self.H]])
        self.data['a_texcoord'] = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])

        VERT_SHADER = """
        // Uniforms
        uniform mat4 u_model;
        uniform mat4 u_view;
        uniform mat4 u_projection;
        uniform float u_antialias;

        // Attributes
        attribute vec2 a_position;
        attribute vec2 a_texcoord;

        // Varyings
        varying vec2 v_texcoord;

        // Main
        void main (void)
        {
            v_texcoord = a_texcoord;
            gl_Position = u_projection * u_view * u_model * vec4(a_position,0.0,1.0);
        }
        """

        FRAG_SHADER = """
        uniform sampler2D u_texture;
        varying vec2 v_texcoord;
        void main()
        {
            gl_FragColor = texture2D(u_texture, v_texcoord);
            gl_FragColor.a = 1.0;
        }

        """

        vispy.app.Canvas.__init__(self, keys='interactive', size=((self.W * 20), (self.H * 20)))

        self.args = args
        print(args)
        if args:
            self.Data_queue = args[0]

        self.program = gloo.Program(VERT_SHADER, FRAG_SHADER)
        self.texture = gloo.Texture2D(colors, interpolation='linear', format='rgba')

        self.program['u_texture'] = self.texture
        self.program.bind(gloo.VertexBuffer(self.data))

        self.view = np.eye(4, dtype=np.float32)
        self.model = np.eye(4, dtype=np.float32)
        self.projection = np.eye(4, dtype=np.float32)

        self.program['u_model'] = self.model
        self.program['u_view'] = self.view
        self.projection = ortho(0, self.W, 0, self.H, -1, 1)
        self.program['u_projection'] = self.projection

        gloo.set_clear_color('white')

        self._timer = vispy.app.Timer('auto', connect=self.update, start=True)

    def on_resize(self, event):
        width, height = event.physical_size
        gloo.set_viewport(0, 0, width, height)
        self.projection = ortho(0, width, 0, height, -100, 100)
        self.program['u_projection'] = self.projection

        # Compute the new size of the quad
        r = width / float(height)
        R = self.W / float(self.H)
        if r < R:
            w, h = width, width / R
            x, y = 0, int((height - h) / 2)
        else:
            w, h = height * R, height
            x, y = int((width - w) / 2), 0
        self.data['a_position'] = np.array(
            [[x, y], [x + w, y], [x, y + h], [x + w, y + h]])
        self.program.bind(gloo.VertexBuffer(self.data))

    def on_draw(self, event):
        gloo.clear(color=True, depth=True)
        if self.args:
            if not self.Data_queue.empty():
                self.I[...] = self.Data_queue.get_nowait()
        else:
            self.I[...] = np.random.uniform(0, 1, (self.W, self.H)).astype(np.float32)

        colors = color.get_colormap("Oranges").map(self.I).reshape(self.I.shape + (-1,))  # YlOrBr
        self.texture.set_data(colors)
        self.program.draw('triangle_strip')

    def show_fps(self, fps):
        print("FPS - %.2f" % fps)