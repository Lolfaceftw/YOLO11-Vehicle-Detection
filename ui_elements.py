import ipywidgets as widgets
from . import config

# --- UI Elements ---\n",
file_uploader = widgets.FileUpload(
    accept='image/*,video/*',
    multiple=False,
    description='Upload File',
    button_style='',
    icon='upload'
)
file_uploader.style.button_color = config.COLOR_PRIMARY

process_button = widgets.Button(
    description='Process Real-time',
    disabled=True,
    button_style='',
    tooltip='Process image or play video with real-time detection',
    icon='cogs'
)
process_button.style.button_color = config.COLOR_ACCENT
process_button.style.text_color = config.COLOR_TEXT_ON_PRIMARY

fast_process_button = widgets.Button(
    description='Fast Process Video',
    disabled=True,
    button_style='',
    tooltip='Process entire video first, then enable playback',
    icon='bolt'
)
fast_process_button.style.button_color = config.COLOR_ORANGE_ACCENT
fast_process_button.style.text_color = config.COLOR_TEXT_ON_PRIMARY

# AVAILABLE_MODELS keys will be dynamically fetched for options
model_selector_radio = widgets.RadioButtons(
    options=[], # To be populated by model_loader
    value=None, # To be set by model_loader
    description='Model:',
    disabled=False,
    style={'description_width': 'initial'}
)

iou_slider = widgets.FloatSlider(
    value=config.DEFAULT_IOU_THRESHOLD,
    min=0.01, max=1.0, step=0.01,
    description='IoU Thresh:',
    disabled=True,
    continuous_update=False,
    readout_format='.2f',
    style={'description_width': 'initial', 'handle_color': config.COLOR_ACCENT}
)

conf_slider = widgets.FloatSlider(
    value=config.DEFAULT_CONF_THRESHOLD,
    min=0.01, max=1.0, step=0.01,
    description='Conf Thresh:',
    disabled=True,
    continuous_update=False,
    readout_format='.2f',
    style={'description_width': 'initial', 'handle_color': config.COLOR_ACCENT}
)

video_display_widget = widgets.Image(
    format='jpeg', width=640, height=640, 
    layout={'visibility': 'visible'}
)
play_pause_button = widgets.Button(
    description="Play", disabled=True, icon='play', 
    style={'button_color': config.COLOR_BUTTON_GREY}
)
stop_button = widgets.Button(
    description="Stop", disabled=True, icon='stop', 
    style={'button_color': config.COLOR_BUTTON_GREY}
)
video_controls = widgets.HBox(
    [play_pause_button, stop_button], 
    layout={'visibility': 'visible'}
)

progress_slider = widgets.IntSlider(
    value=0, min=0, max=100, # Max will be updated based on video
    description='Progress:',
    disabled=True,
    continuous_update=False, # Important for debouncing/performance
    style={'description_width': 'initial', 'handle_color': config.COLOR_ACCENT},
    layout=widgets.Layout(width='calc(100% - 120px)')
)
time_label = widgets.Label(
    value="00:00 / 00:00", 
    layout=widgets.Layout(width='110px')
)
progress_slider_hbox = widgets.HBox(
    [progress_slider, time_label], 
    layout={'visibility': 'visible', 'width':'100%', 'align_items':'center'}
)

loading_spinner_html_content = f"""
<style>
.loader-custom {{ border: 6px solid #f3f3f3; border-top: 6px solid {config.COLOR_PRIMARY}; border-radius: 50%; width: 50px; height: 50px; animation: spin-custom 1s linear infinite; margin: auto; }}
@keyframes spin-custom {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
</style>
<div class='loader-custom'></div>
"""
loading_spinner_html = widgets.HTML(loading_spinner_html_content)

loading_message_label = widgets.Label(
    "Loading...", 
    layout=widgets.Layout(margin='15px auto', font_weight='bold')
)
loading_overlay_content_box = widgets.VBox(
    [loading_spinner_html, loading_message_label],
    layout=widgets.Layout(width='100%', height='100%', align_items='center', justify_content='center', background='rgba(255,255,255,0.85)')
)

fast_progress_bar = widgets.IntProgress(
    value=0,
    min=0,
    max=100, 
    description='Fast Progress:',
    bar_style='info', 
    orientation='horizontal',
    visible=False, 
    layout=widgets.Layout(width='95%', margin='5px 0 5px 0')
)

# Output areas
main_output_area = widgets.Output()
processed_image_display_area = widgets.Output()


# List of general interactive controls for enabling/disabling
interactive_controls_general = [
    file_uploader, process_button, fast_process_button, model_selector_radio, 
    iou_slider, conf_slider
]