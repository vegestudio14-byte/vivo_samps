import os
import json
import kivy
import threading
import time
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.progressbar import ProgressBar
from kivy.uix.filechooser import FileChooserListView  # Corrección de la importación faltante
from kivy.uix.spinner import Spinner
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
from kivy.utils import platform
from kivy.clock import Clock

Window.size = (1024, 600)

class BotoneraVIVOSamps(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10

        # ---- CONFIGURACIÓN DE RUTAS ----
        base_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'VIVO_SAMPS')
        self.path_songs = os.path.join(base_dir, 'SONGS')
        self.path_samps = os.path.join(base_dir, 'SAMPS')
        self.path_base = base_dir

        os.makedirs(self.path_songs, exist_ok=True)
        os.makedirs(self.path_samps, exist_ok=True)

        # ---- BANCO DE MEMORIA RAM ----
        self.banco_songs_ram = {}       
        self.playlist_rutas = []       
        self.playlist_sounds = []      
        self.current_index = -1       
        self.is_paused = False       
        
        self.music_position = 0      
        self.music_length = 0        
        self.clock_event = None      
        self.fade_clock_event = None
        self.bloquear_fader_update = False 

        # ---- DICCIONARIOS PADS ----
        self.pads_dict = {}         
        self.audio_paths = {}       
        self.audio_objects = {}     

        # =========================================================================
        # INTERFAZ GRÁFICA PRINCIPAL
        # =========================================================================
        self.layout_principal = BoxLayout(orientation='vertical', spacing=10)
        
        # --- REPRODUCTOR MASTER ---
        barra_reproductor_master = BoxLayout(orientation='vertical', size_hint_y=0.25, spacing=5)
        
        layout_lcd = BoxLayout(orientation='horizontal', spacing=10)
        self.lbl_lcd_sonando = Label(text='[ SONANDO ]: Ninguna', bold=True, color=[0.2, 0.9, 0.2, 1], halign='left', valign='middle')
        self.lbl_lcd_sonando.bind(size=self.lbl_lcd_sonando.setter('text_size'))
        
        self.lbl_lcd_siguiente = Label(text='[ SIGUIENTE ]: Ninguna', bold=True, color=[0.9, 0.6, 0.1, 1], halign='left', valign='middle')
        self.lbl_lcd_siguiente.bind(size=self.lbl_lcd_siguiente.setter('text_size'))
        
        layout_lcd.add_widget(self.lbl_lcd_sonando)
        layout_lcd.add_widget(self.lbl_lcd_siguiente)
        barra_reproductor_master.add_widget(layout_lcd)
        
        layout_controles_linea = BoxLayout(orientation='horizontal', spacing=10)
        
        self.btn_add_playlist = Button(text='[ + TRACK ]', size_hint_x=0.12, bold=True, background_color=[0.2, 0.6, 0.8, 1])
        self.btn_add_playlist.bind(on_press=self.abrir_banco_ram_visual)
        
        centro_sliders = BoxLayout(orientation='vertical', size_hint_x=0.45, spacing=2)
        layout_fader = BoxLayout(orientation='horizontal')
        layout_fader.add_widget(Label(text="TIEMPO:", size_hint_x=0.2, font_size='11sp'))
        self.fader_tiempo = Slider(min=0, max=100, value=0, size_hint_x=0.8)
        self.fader_tiempo.bind(on_touch_down=self.fader_touch_down, on_touch_up=self.fader_touch_up)
        layout_fader.add_widget(self.fader_tiempo)
        
        layout_vol = BoxLayout(orientation='horizontal')
        layout_vol.add_widget(Label(text="VOLUMEN:", size_hint_x=0.2, font_size='11sp'))
        self.slider_vol = Slider(min=0, max=1, value=1, step=0.05, size_hint_x=0.8)
        self.slider_vol.bind(value=self.cambiar_volumen_master_playlist)
        layout_vol.add_widget(self.slider_vol)
        
        centro_sliders.add_widget(layout_fader)
        centro_sliders.add_widget(layout_vol)

        self.btn_play_fusion = Button(text='FUSION\n[ >> ]', size_hint_x=0.14, background_color=[0.1, 0.6, 0.1, 1], bold=True, halign='center')
        self.btn_pause = Button(text='PAUSE', size_hint_x=0.13, background_color=[0.6, 0.6, 0.1, 1], bold=True)
        self.btn_stop = Button(text='STOP', size_hint_x=0.13, background_color=[0.7, 0.1, 0.1, 1], bold=True)
        self.btn_ver_lista = Button(text='VER\nLISTA', size_hint_x=0.11, background_color=[0.4, 0.4, 0.4, 1], halign='center', font_size='12sp')

        self.btn_play_fusion.bind(on_press=self.disparar_play_o_fusion)
        self.btn_pause.bind(on_press=self.pause_playlist)
        self.btn_stop.bind(on_press=self.stop_playlist)
        self.btn_ver_lista.bind(on_press=self.abrir_popup_gestion_playlist)

        layout_controles_linea.add_widget(self.btn_add_playlist)
        layout_controles_linea.add_widget(centro_sliders)
        layout_controles_linea.add_widget(self.btn_play_fusion)
        layout_controles_linea.add_widget(self.btn_pause)
        layout_controles_linea.add_widget(self.btn_stop)
        layout_controles_linea.add_widget(self.btn_ver_lista)
        barra_reproductor_master.add_widget(layout_controles_linea)
        self.layout_principal.add_widget(barra_reproductor_master)

        # --- CUERPO PADS ---
        cuerpo_principal = BoxLayout(orientation='horizontal', size_hint_y=0.75, spacing=10)
        panel_pads = GridLayout(cols=6, rows=4, spacing=8, size_hint_x=0.85)
        for i in range(1, 25):
            btn_pad = Button(text=f"{i}\n[Vacio]", halign='center', valign='middle', background_color=[0.2, 0.2, 0.2, 1])
            btn_pad.bind(size=btn_pad.setter('text_size'))
            btn_pad.bind(on_press=lambda instance, num=i: self.ejecutar_pad(num))
            self.pads_dict[i] = btn_pad
            panel_pads.add_widget(btn_pad)

        barra_lateral = BoxLayout(orientation='vertical', size_hint_x=0.15, spacing=10)
        self.btn_listado = Button(text='LISTA\n[ ? ]', halign='center', background_color=[0.4, 0.2, 0.6, 1])
        self.btn_lapiz = Button(text='ASIGNAR\n[ Editar ]', halign='center', background_color=[0.8, 0.5, 0.1, 1], bold=True)
        self.btn_config = Button(text='SET\n[ JSON ]', halign='center', background_color=[0.1, 0.4, 0.4, 1])
        self.btn_panic = Button(text='PANIC\n[ !!! ]', halign='center', background_color=[0.9, 0, 0, 1], bold=True)
        self.btn_cerrar = Button(text='SALIR\n[ X ]', halign='center', background_color=[0.3, 0.3, 0.3, 1])

        self.btn_listado.bind(on_press=self.mostrar_listado)
        self.btn_lapiz.bind(on_press=self.abrir_dialogo_asignacion)
        self.btn_config.bind(on_press=self.abrir_menu_config_json)
        self.btn_panic.bind(on_press=self.panic_stop_total)
        self.btn_cerrar.bind(on_press=App.get_running_app().stop)

        barra_lateral.add_widget(self.btn_listado)
        barra_lateral.add_widget(self.btn_lapiz)
        barra_lateral.add_widget(self.btn_config)
        barra_lateral.add_widget(self.btn_panic)
        barra_lateral.add_widget(self.btn_cerrar)

        cuerpo_principal.add_widget(panel_pads)
        cuerpo_principal.add_widget(barra_lateral)
        self.layout_principal.add_widget(cuerpo_principal)

        # =========================================================================
        # INTERFAZ DEL SPLASH SCREEN
        # =========================================================================
        self.layout_splash = BoxLayout(orientation='vertical', padding=50, spacing=20)
        self.lbl_splash_titulo = Label(text="VIVO! SAMPS v1.0", font_size='34sp', bold=True, color=[0.2, 0.6, 0.8, 1], size_hint_y=0.4)
        self.lbl_splash_estado = Label(text="Iniciando sistema...", font_size='16sp', size_hint_y=0.2)
        self.barra_progreso = ProgressBar(max=100, value=0, size_hint_y=0.2)
        self.lbl_splash_porcentaje = Label(text="0%", font_size='18sp', bold=True, color=[0.9, 0.6, 0.1, 1], size_hint_y=0.2)

        self.layout_splash.add_widget(self.lbl_splash_titulo)
        self.layout_splash.add_widget(self.lbl_splash_estado)
        self.layout_splash.add_widget(self.barra_progreso)
        self.layout_splash.add_widget(self.lbl_splash_porcentaje)

        self.add_widget(self.layout_splash)

        Clock.schedule_once(lambda dt: threading.Thread(target=self.subproceso_precargar_toda_la_carpeta, daemon=True).start(), 0.2)

    # ---- INDEXACIÓN ASÍNCRONA EN MEMORIA ----
    def subproceso_precargar_toda_la_carpeta(self):
        try:
            archivos = [f for f in os.listdir(self.path_songs) if f.endswith('.mp3')]
        except:
            archivos = []

        total_archivos = len(archivos)

        if total_archivos == 0:
            Clock.schedule_once(lambda dt: self.finalizar_indexacion_ram(), 0.5)
            return

        for idx, f in enumerate(archivos):
            ruta_completa = os.path.join(self.path_songs, f)
            Clock.schedule_once(lambda dt, name=f: self.actualizar_texto_splash(name), 0)
            
            audio_objeto = SoundLoader.load(ruta_completa)
            if audio_objeto:
                self.banco_songs_ram[f] = audio_objeto
            
            porcentaje = int(((idx + 1) / total_archivos) * 100)
            Clock.schedule_once(lambda dt, val=porcentaje: self.actualizar_barra_splash(val), 0)
            time.sleep(0.1)
        
        Clock.schedule_once(lambda dt: self.finalizar_indexacion_ram(), 0.5)

    def actualizar_texto_splash(self, nombre_archivo):
        self.lbl_splash_estado.text = f"[ CARGANDO LIBRERÍA ]: {nombre_archivo}"

    def actualizar_barra_splash(self, valor):
        self.barra_progreso.value = valor
        self.lbl_splash_porcentaje.text = f"{valor}%"

    def finalizar_indexacion_ram(self):
        self.clear_widgets()
        self.add_widget(self.layout_principal)
        print(f"[RAM CORE] {len(self.banco_songs_ram)} temas montados con éxito.")

    # ---- REPRODUCTOR EN RAM ----
    def abrir_banco_ram_visual(self, instance):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        if not self.banco_songs_ram:
            box.add_widget(Label(text="No hay canciones pre-cargadas en /SONGS/"))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=5, size_hint_y=None)
            grid.bind(minimum_height=grid.setter('height'))
            
            for nombre_archivo in self.banco_songs_ram.keys():
                btn = Button(text=nombre_archivo, size_hint_y=None, height=45, background_color=[0.15, 0.35, 0.45, 1])
                btn.bind(on_press=lambda inst, name=nombre_archivo: self.inyectar_desde_ram(name))
                grid.add_widget(btn)
                
            scroll.add_widget(grid)
            box.add_widget(scroll)
            
        btn_cerrar = Button(text="Cancelar", size_hint_y=0.15)
        box.add_widget(btn_cerrar)
        self.popup_ram = Popup(title="Seleccionar Pista (Carga Instantánea de RAM)", content=box, size_hint=(0.7, 0.8))
        self.popup_ram.open()
        btn_cerrar.bind(on_press=self.popup_ram.dismiss)

    def inyectar_desde_ram(self, nombre_archivo):
        self.popup_ram.dismiss()
        audio_objeto = self.banco_songs_ram[nombre_archivo]
        
        self.playlist_rutas.append(os.path.join(self.path_songs, nombre_archivo))
        self.playlist_sounds.append(audio_objeto)
        self.actualizar_pantallas_lcd()

    def actualizar_pantallas_lcd(self):
        if self.current_index >= 0 and self.current_index < len(self.playlist_rutas):
            self.lbl_lcd_sonando.text = f"[ SONANDO ]: {os.path.basename(self.playlist_rutas[self.current_index])}"
        else:
            self.lbl_lcd_sonando.text = "[ SONANDO ]: Ninguna"

        sig_idx = self.current_index + 1
        if sig_idx < len(self.playlist_rutas):
            self.lbl_lcd_siguiente.text = f"[ SIGUIENTE ]: {os.path.basename(self.playlist_rutas[sig_idx])}"
        else:
            self.lbl_lcd_siguiente.text = "[ SIGUIENTE ]: Fin de la lista"

    def disparar_play_o_fusion(self, instance):
        if not self.playlist_sounds:
            return

        if self.is_paused:
            track_actual = self.playlist_sounds[self.current_index]
            track_actual.play()
            self.is_paused = False
            self.iniciar_reloj()
            return

        if self.current_index == -1:
            self.current_index = 0
            self.ejecutar_track_inicial()
        else:
            sig_idx = self.current_index + 1
            if sig_idx < len(self.playlist_sounds):
                self.parar_reloj()
                
                track_viejo = self.playlist_sounds[self.current_index]
                self.current_index = sig_idx
                track_nuevo = self.playlist_sounds[self.current_index]
                
                track_nuevo.volume = 0
                track_nuevo.play()
                
                self.music_length = track_nuevo.length
                self.fader_tiempo.max = self.music_length
                self.fader_tiempo.value = 0
                self.music_position = 0
                
                vol_max = self.slider_vol.value
                threading.Thread(target=self.subproceso_crossfade, args=(track_viejo, track_nuevo, vol_max), daemon=True).start()

    def ejecutar_track_inicial(self):
        self.parar_reloj()
        track_actual = self.playlist_sounds[self.current_index]
        track_actual.volume = self.slider_vol.value
        track_actual.play()
        
        self.music_length = track_actual.length
        self.fader_tiempo.max = self.music_length
        self.fader_tiempo.value = 0
        self.music_position = 0
        
        self.is_paused = False
        self.actualizar_pantallas_lcd()
        self.iniciar_reloj()

    def subproceso_crossfade(self, t_out, t_in, vol_max):
        steps = 20
        for step in range(1, steps + 1):
            ratio = step / steps
            t_out.volume = max(0.0, vol_max * (1.0 - ratio))
            t_in.volume = min(vol_max, vol_max * ratio)
            time.sleep(0.05)
            
        t_out.stop()
        Clock.schedule_once(lambda dt: self.actualizar_pantallas_lcd(), 0)
        Clock.schedule_once(lambda dt: self.iniciar_reloj(), 0)

    def pause_playlist(self, instance):
        if self.current_index != -1 and self.current_index < len(self.playlist_sounds):
            self.parar_reloj()
            self.playlist_sounds[self.current_index].stop()
            self.is_paused = True
            self.lbl_lcd_sonando.text = "[ PAUSA ACTIVA ]"

    def stop_playlist(self, instance):
        self.parar_reloj()
        for track in self.playlist_sounds:
            track.stop()
        self.current_index = -1
        self.music_position = 0
        self.fader_tiempo.value = 0
        self.is_paused = False
        self.actualizar_pantallas_lcd()

    def actualizar_reloj(self, dt):
        if self.current_index != -1 and self.current_index < len(self.playlist_sounds):
            track = self.playlist_sounds[self.current_index]
            if track.state == 'play':
                if not self.bloquear_fader_update:
                    self.music_position = track.get_pos()
                    self.fader_tiempo.value = min(self.music_position, self.music_length)
            else:
                if not self.is_paused:
                    sig_idx = self.current_index + 1
                    if sig_idx < len(self.playlist_sounds):
                        self.current_index = sig_idx
                        self.ejecutar_track_inicial()
                    else:
                        self.stop_playlist(None)

    def iniciar_reloj(self):
        if not self.clock_event:
            self.clock_event = Clock.schedule_interval(self.actualizar_reloj, 1.0)

    def parar_reloj(self):
        if self.clock_event:
            Clock.unschedule(self.clock_event)
            self.clock_event = None

    def fader_touch_down(self, instance, touch):
        if instance.collide_point(*touch.pos):
            self.bloquear_fader_update = True

    def fader_touch_up(self, instance, touch):
        if instance.collide_point(*touch.pos) and self.bloquear_fader_update:
            self.bloquear_fader_update = False
            self.music_position = self.fader_tiempo.value
            if self.current_index != -1:
                track = self.playlist_sounds[self.current_index]
                track.seek(self.music_position)

    def cambiar_volumen_master_playlist(self, instance, valor):
        if self.current_index != -1 and self.current_index < len(self.playlist_sounds):
            self.playlist_sounds[self.current_index].volume = valor

    # ---- POPUP GESTIÓN PLAYLIST ----
    def abrir_popup_gestion_playlist(self, instance):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        texto_lista = "--- ORDEN DEL PLAYLIST ACTUAL ---\n"
        if not self.playlist_rutas: texto_lista += "[ Lista vacia ]"
        else:
            for idx, r in enumerate(self.playlist_rutas):
                puntero = " -> " if idx == self.current_index else "    "
                texto_lista += f"{puntero}{idx + 1}. {os.path.basename(r)}\n"
                
        box.add_widget(Label(text=texto_lista, halign='left', valign='top', size_hint_y=0.5))
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=0.25)
        btn_save_pl = Button(text="Guardar Lista\n(JSON)", halign='center', background_color=[0.2, 0.6, 0.4, 1])
        btn_load_pl = Button(text="Cargar Lista\n(JSON)", halign='center', background_color=[0.2, 0.4, 0.6, 1])
        btn_limpiar = Button(text="Limpiar\nLista", halign='center', background_color=[0.7, 0.1, 0.1, 1])
        
        btn_layout.add_widget(btn_save_pl)
        btn_layout.add_widget(btn_load_pl)
        btn_layout.add_widget(btn_limpiar)
        box.add_widget(btn_layout)
        
        btn_cerrar = Button(text="Regresar", size_hint_y=0.15)
        box.add_widget(btn_cerrar)
        popup = Popup(title="Administrador de Playlist", content=box, size_hint=(0.6, 0.8))
        popup.open()
        
        btn_cerrar.bind(on_press=popup.dismiss)
        btn_limpiar.bind(on_press=lambda x: [self.playlist_rutas.clear(), self.playlist_sounds.clear(), self.stop_playlist(None), popup.dismiss()])
        btn_save_pl.bind(on_press=lambda x: [popup.dismiss(), self.guardar_playlist_json()])
        btn_load_pl.bind(on_press=lambda x: [popup.dismiss(), self.abrir_explorador_json_playlist()])

    def guardar_playlist_json(self):
        try:
            with open(os.path.join(self.path_base, "Playlist_Default.json"), "w", encoding="utf-8") as f:
                json.dump({"playlist": self.playlist_rutas}, f, indent=4, ensure_ascii=False)
        except Exception as e: print(e)

    def abrir_explorador_json_playlist(self):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        filechooser = FileChooserListView(path=self.path_base, filters=['*.json'])
        box.add_widget(filechooser)
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=0.15)
        btn_cargar = Button(text="Cargar Playlist", background_color=[0.1, 0.6, 0.6, 1], bold=True)
        btn_cancelar = Button(text="Cancelar")
        btn_layout.add_widget(btn_cargar)
        btn_layout.add_widget(btn_cancelar)
        box.add_widget(btn_layout)
        popup = Popup(title="Seleccionar Playlist JSON", content=box, size_hint=(0.7, 0.8))
        popup.open()
        btn_cancelar.bind(on_press=popup.dismiss)
        
        def confirmar(inst):
            if filechooser.selection:
                try:
                    with open(filechooser.selection[0], "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.playlist_rutas = data.get("playlist", [])
                    self.playlist_sounds.clear()
                    self.stop_playlist(None)
                    
                    for r in self.playlist_rutas:
                        name = os.path.basename(r)
                        if name in self.banco_songs_ram:
                            self.playlist_sounds.append(self.banco_songs_ram[name])
                    self.actualizar_pantallas_lcd()
                except Exception as e: print(e)
            popup.dismiss()
        btn_cargar.bind(on_press=confirmar)

    # ---- MÓDULO SAMPLES (PADS ORIGINALES) ----
    def abrir_dialogo_asignacion(self, instance):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        box.add_widget(Label(text="1. Selecciona el archivo de sonido (.mp3):", size_hint_y=0.1))
        
        # Aquí es donde fallaba: FileChooserListView ahora sí está definido
        filechooser = FileChooserListView(path=self.path_samps, filters=['*.mp3'], size_hint_y=0.5)
        box.add_widget(filechooser)
        
        opciones_spinner = [f"Boton {i} - {'[X] Ocupado' if i in self.audio_paths else '[V] Libre'}" for i in range(1, 25)]
        box.add_widget(Label(text="2. Elige el boton destino:", size_hint_y=0.1))
        spinner_botones = Spinner(text='Selecciona un boton...', values=opciones_spinner, size_hint_y=0.12, background_color=[0.2, 0.5, 0.5, 1])
        box.add_widget(spinner_botones)
        
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=0.18)
        btn_confirmar = Button(text="Asignar Sonido", background_color=[0.1, 0.6, 0.1, 1], bold=True)
        btn_cancelar = Button(text="Cancelar")
        btn_layout.add_widget(btn_confirmar)
        btn_layout.add_widget(btn_cancelar)
        box.add_widget(btn_layout)
        popup = Popup(title="Asignador Visual de Samples", content=box, size_hint=(0.8, 0.9))
        popup.open()
        btn_cancelar.bind(on_press=popup.dismiss)
        
        def procesar(inst):
            if not filechooser.selection or spinner_botones.text == 'Selecciona un boton...': return
            ruta_archivo = filechooser.selection[0]
            num_pad = int(spinner_botones.text.split(" ")[1])
            popup.dismiss()
            self.validar_y_asignar(ruta_archivo, num_pad)
        btn_confirmar.bind(on_press=procesar)

    def validar_y_asignar(self, ruta_archivo, num_pad):
        if num_pad in self.audio_paths:
            box_alerta = BoxLayout(orientation='vertical', padding=10, spacing=10)
            box_alerta.add_widget(Label(text=f"El boton {num_pad} esta ocupado.\n¿Reemplazar?"))
            btn_layout = BoxLayout(orientation='horizontal', spacing=10)
            btn_si = Button(text="Si", background_color=[0.8, 0.1, 0.1, 1])
            btn_no = Button(text="No")
            btn_layout.add_widget(btn_si)
            btn_layout.add_widget(btn_no)
            box_alerta.add_widget(btn_layout)
            popup = Popup(title="Advertencia", content=box_alerta, size_hint=(0.4, 0.35))
            popup.open()
            btn_no.bind(on_press=lambda x: [popup.dismiss(), self.abrir_dialogo_asignacion(None)])
            btn_si.bind(on_press=lambda x: [popup.dismiss(), self.cargar_sonido_en_pad(ruta_archivo, num_pad)])
        else: self.cargar_sonido_en_pad(ruta_archivo, num_pad)

    def cargar_sonido_en_pad(self, ruta_archivo, num_pad):
        sound = SoundLoader.load(ruta_archivo)
        if sound:
            if num_pad in self.audio_objects and self.audio_objects[num_pad]: self.audio_objects[num_pad].unload()
            self.audio_paths[num_pad] = ruta_archivo
            self.audio_objects[num_pad] = sound
            self.pads_dict[num_pad].text = f"{num_pad}\n{os.path.basename(ruta_archivo)}"
            self.pads_dict[num_pad].background_color = [0, 0.4, 0.8, 1]

    def ejecutar_pad(self, num_pad):
        if num_pad in self.audio_objects and self.audio_objects[num_pad]:
            sound = self.audio_objects[num_pad]
            if sound.state == 'play':
                sound.stop()
                self.pads_dict[num_pad].background_color = [0, 0.4, 0.8, 1]
            else:
                sound.play()
                self.pads_dict[num_pad].background_color = [1, 0.5, 0, 1]

    def abrir_menu_config_json(self, instance):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        box.add_widget(Label(text="CONFIGURACION DE PADS", bold=True))
        btn_guardar = Button(text="Guardar Armado Actual (Set_Default.json)", background_color=[0.2, 0.6, 0.4, 1])
        btn_cargar = Button(text="Cargar Set Guardado (.json)", background_color=[0.2, 0.4, 0.6, 1])
        btn_cancelar = Button(text="Regresar")
        box.add_widget(btn_guardar)
        box.add_widget(btn_cargar)
        box.add_widget(btn_cancelar)
        popup = Popup(title="Menu Respaldo Pads", content=box, size_hint=(0.5, 0.45))
        popup.open()
        btn_cancelar.bind(on_press=popup.dismiss)
        btn_guardar.bind(on_press=lambda x: [popup.dismiss(), self.guarda_armado_json()])
        btn_cargar.bind(on_press=lambda x: [popup.dismiss(), self.abrir_explorador_json_pads()])

    def guarda_armado_json(self):
        data = {"pads": {str(i): self.audio_paths.get(i, None) for i in range(1, 25)}}
        try:
            with open(os.path.join(self.path_base, "Set_Default.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e: print(e)

    def abrir_explorador_json_pads(self):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        filechooser = FileChooserListView(path=self.path_base, filters=['*.json'])
        box.add_widget(filechooser)
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=0.15)
        btn_cargar = Button(text="Cargar Pads", background_color=[0.1, 0.6, 0.6, 1], bold=True)
        btn_cancelar = Button(text="Cancelar")
        btn_layout.add_widget(btn_cargar)
        btn_layout.add_widget(btn_cancelar)
        box.add_widget(btn_layout)
        popup = Popup(title="Seleccionar JSON de Pads", content=box, size_hint=(0.7, 0.8))
        popup.open()
        btn_cancelar.bind(on_press=popup.dismiss)
        
        def confirmar(inst):
            if filechooser.selection:
                try:
                    with open(filechooser.selection[0], "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for i in range(1, 25):
                        if i in self.audio_objects and self.audio_objects[i]: self.audio_objects[i].unload()
                        self.pads_dict[i].text = f"{i}\n[Vacio]"
                        self.pads_dict[i].background_color = [0.2, 0.2, 0.2, 1]
                    self.audio_paths.clear()
                    self.audio_objects.clear()
                    for str_id, r in data.get("pads", {}).items():
                        if r and os.path.exists(r):
                            num = int(str_id)
                            sound = SoundLoader.load(r)
                            if sound:
                                self.audio_paths[num] = r
                                self.audio_objects[num] = sound
                                self.pads_dict[num].text = f"{num}\n{os.path.basename(r)}"
                                self.pads_dict[num].background_color = [0, 0.4, 0.8, 1]
                except Exception as e: print(e)
            popup.dismiss()
        btn_cargar.bind(on_press=confirmar)

    def mostrar_listado(self, instance):
        texto = "".join([f"{i} - {os.path.basename(self.audio_paths[i]) if i in self.audio_paths else '[Vacio]'}\n" for i in range(1, 25)])
        box = BoxLayout(orientation='vertical', padding=10)
        box.add_widget(Label(text=texto, halign='left', valign='top'))
        btn = Button(text="Cerrar Lista", size_hint_y=0.15)
        box.add_widget(btn)
        popup = Popup(title="Acordeon de Asignaciones", content=box, size_hint=(0.6, 0.9))
        popup.open()
        btn.bind(on_press=popup.dismiss)

    def panic_stop_total(self, instance):
        self.parar_reloj()
        for track in self.playlist_sounds:
            track.stop()
        self.music_position = 0
        self.fader_tiempo.value = 0
        self.is_paused = False
        self.current_index = -1
        self.actualizar_pantallas_lcd()
        for sound in self.audio_objects.values():
            if sound: sound.stop()
        for num_pad, sound in self.audio_objects.items():
            if sound: self.pads_dict[num_pad].background_color = [0, 0.4, 0.8, 1]

class VIVOSampsApp(App):
    def build(self):
        self.title = 'VIVO SAMPS v1.0 [RAM FIXED SPLASH]'
        return BotoneraVIVOSamps()

if __name__ == '__main__':
    VIVOSampsApp().run()