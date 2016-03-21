import psutil, os

def setDisplayToLocalX():
    """
    set DISPLAY env var in this process to the id of the X process on localhost

    I might need something like xauth merge /run/gdm/auth-for-gdm-xxxxxx/database too
    and this isn't automated yet
    """
    for pid in psutil.get_pid_list():
        try:
            proc = psutil.Process(pid)
            if proc.exe not in ['/usr/bin/Xorg', '/usr/bin/X', '/usr/bin/X11/X']:
                continue
        except (psutil.error.AccessDenied, psutil.error.NoSuchProcess):
            continue
        display = [arg for arg in proc.cmdline if not arg.startswith('-')][1]
        if display == 'tcp': # ??
            display = ":0.0"
        assert display.startswith(':'), display
        os.environ['DISPLAY'] = display
        os.environ['XAUTHORITY'] = os.path.expanduser('~/.Xauthority')
        break
    else:
        raise ValueError("didn't find an Xorg process")
