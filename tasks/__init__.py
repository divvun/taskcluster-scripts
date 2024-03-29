from .lang_task import create_lang_tasks
from .kbd_task import create_kbd_tasks
from .pahkat import create_pahkat_tasks
from .pahkat_reposrv import (
    create_pahkat_reposrv_task,
    create_pahkat_reposrv_release_task,
)
from .ansible import create_ansible_task
from .divvun_manager_macos import create_divvun_manager_macos_task
from .divvun_manager_windows import create_divvun_manager_windows_tasks
from .libreoffice import create_libreoffice_tasks
from .spelli import create_spelli_task
from .windivvun import create_windivvun_tasks
from .divvun_keyboard import create_divvun_keyboard_tasks
from .gut import create_gut_tasks
from .kbdi import create_kbdi_tasks
from .kbdgen import create_kbdgen_tasks
from .mso_resources import create_mso_resources_tasks, create_mso_patch_gen_task
from .divvunspell import create_divvunspell_tasks
from .omegat import create_omegat_tasks
from .hooks.mirror_cleanup import create_mirror_cleanup_task
from .macdivvun import create_macdivvun_task
