# -*- coding: utf-8 -*-
"""Minimal Win32 adapter used by traybar.py."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

if not hasattr(wintypes, "LRESULT"):
    wintypes.LRESULT = ctypes.c_ssize_t

if not hasattr(wintypes, "ULONG_PTR"):
    if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_ulonglong):
        wintypes.ULONG_PTR = ctypes.c_ulonglong
    else:
        wintypes.ULONG_PTR = ctypes.c_ulong

for _name in [
    "HCURSOR",
    "HICON",
    "HBRUSH",
    "HINSTANCE",
    "HMODULE",
    "HBITMAP",
    "HGDIOBJ",
    "HDC",
    "HMENU",
]:
    if not hasattr(wintypes, _name):
        setattr(wintypes, _name, wintypes.HANDLE)

if not hasattr(wintypes, "ATOM"):
    wintypes.ATOM = wintypes.WORD


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_USER = 0x0400
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

WS_OVERLAPPED = 0x00000000
WS_SYSMENU = 0x00080000
CW_USEDEFAULT = 0x80000000

CS_VREDRAW = 0x0001
CS_HREDRAW = 0x0002

IDC_ARROW = 32512
COLOR_WINDOW = 5
COLOR_MENU = 4

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDI_APPLICATION = 32512

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

TPM_LEFTALIGN = 0x0000

SM_CXSMICON = 49
SM_CYSMICON = 50
DI_NORMAL = 0x0003

MIIM_BITMAP = 0x00000080
MIIM_ID = 0x00000002
MIIM_STRING = 0x00000040
MIIM_SUBMENU = 0x00000004


WNDPROC = ctypes.WINFUNCTYPE(
    wintypes.LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
LPFN_WNDPROC = WNDPROC

HANDLE = wintypes.HANDLE
WPARAM = wintypes.WPARAM
LPARAM = wintypes.LPARAM


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MENUITEMINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("fMask", wintypes.UINT),
        ("fType", wintypes.UINT),
        ("fState", wintypes.UINT),
        ("wID", wintypes.UINT),
        ("hSubMenu", wintypes.HMENU),
        ("hbmpChecked", wintypes.HBITMAP),
        ("hbmpUnchecked", wintypes.HBITMAP),
        ("dwItemData", wintypes.ULONG_PTR),
        ("dwTypeData", wintypes.LPWSTR),
        ("cch", wintypes.UINT),
        ("hbmpItem", wintypes.HBITMAP),
    ]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


DefWindowProc = user32.DefWindowProcW
DefWindowProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
DefWindowProc.restype = wintypes.LRESULT

RegisterClass = user32.RegisterClassW
RegisterClass.argtypes = [ctypes.POINTER(WNDCLASS)]
RegisterClass.restype = wintypes.ATOM

CreateWindowEx = user32.CreateWindowExW
CreateWindowEx.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
CreateWindowEx.restype = wintypes.HWND

UpdateWindow = user32.UpdateWindow
UpdateWindow.argtypes = [wintypes.HWND]

PostMessage = user32.PostMessageW
PostMessage.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

DestroyWindow = user32.DestroyWindow
DestroyWindow.argtypes = [wintypes.HWND]

PostQuitMessage = user32.PostQuitMessage
PostQuitMessage.argtypes = [ctypes.c_int]

LoadCursor = user32.LoadCursorW
LoadCursor.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
LoadCursor.restype = wintypes.HCURSOR

LoadIcon = user32.LoadIconW
LoadIcon.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
LoadIcon.restype = wintypes.HICON

LoadImage = user32.LoadImageW
LoadImage.argtypes = [
    wintypes.HINSTANCE,
    wintypes.LPCWSTR,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
LoadImage.restype = wintypes.HANDLE

SetForegroundWindow = user32.SetForegroundWindow
SetForegroundWindow.argtypes = [wintypes.HWND]

TrackPopupMenu = user32.TrackPopupMenu
TrackPopupMenu.argtypes = [
    wintypes.HMENU,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    ctypes.POINTER(RECT),
]

CreatePopupMenu = user32.CreatePopupMenu
CreatePopupMenu.restype = wintypes.HMENU

InsertMenuItem = user32.InsertMenuItemW
InsertMenuItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.BOOL, ctypes.POINTER(MENUITEMINFO)]

GetCursorPos = user32.GetCursorPos
GetCursorPos.argtypes = [ctypes.POINTER(POINT)]

GetSystemMetrics = user32.GetSystemMetrics
GetSystemMetrics.argtypes = [ctypes.c_int]

GetDC = user32.GetDC
GetDC.argtypes = [wintypes.HWND]
GetDC.restype = wintypes.HDC

CreateCompatibleDC = gdi32.CreateCompatibleDC
CreateCompatibleDC.argtypes = [wintypes.HDC]
CreateCompatibleDC.restype = wintypes.HDC

CreateCompatibleBitmap = gdi32.CreateCompatibleBitmap
CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
CreateCompatibleBitmap.restype = wintypes.HBITMAP

SelectObject = gdi32.SelectObject
SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
SelectObject.restype = wintypes.HGDIOBJ

DeleteDC = gdi32.DeleteDC
DeleteDC.argtypes = [wintypes.HDC]

DestroyIcon = user32.DestroyIcon
DestroyIcon.argtypes = [wintypes.HICON]

GetSysColorBrush = user32.GetSysColorBrush
GetSysColorBrush.argtypes = [ctypes.c_int]
GetSysColorBrush.restype = wintypes.HBRUSH

FillRect = user32.FillRect
FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(RECT), wintypes.HBRUSH]

DrawIconEx = user32.DrawIconEx
DrawIconEx.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HICON,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
    wintypes.HBRUSH,
    wintypes.UINT,
]

RegisterWindowMessage = user32.RegisterWindowMessageW
RegisterWindowMessage.argtypes = [wintypes.LPCWSTR]
RegisterWindowMessage.restype = wintypes.UINT

GetModuleHandle = kernel32.GetModuleHandleW
GetModuleHandle.argtypes = [wintypes.LPCWSTR]
GetModuleHandle.restype = wintypes.HMODULE

Shell_NotifyIcon = shell32.Shell_NotifyIconW
Shell_NotifyIcon.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]
Shell_NotifyIcon.restype = wintypes.BOOL


def encode_for_locale(value):
    return value


def NotifyData(hwnd, uid, flags=0, callback_message=0, hicon=0, tip=""):
    data = NOTIFYICONDATA()
    data.cbSize = ctypes.sizeof(NOTIFYICONDATA)
    data.hWnd = hwnd
    data.uID = uid
    data.uFlags = flags
    data.uCallbackMessage = callback_message
    data.hIcon = hicon
    data.szTip = str(tip)[:127]
    return data


def PackMENUITEMINFO(text="", hbmpItem=None, wID=None, hSubMenu=None):
    item = MENUITEMINFO()
    item.cbSize = ctypes.sizeof(MENUITEMINFO)
    item.fMask = MIIM_STRING
    item.dwTypeData = ctypes.c_wchar_p(str(text))
    item.cch = len(str(text))
    if hbmpItem is not None:
        item.fMask |= MIIM_BITMAP
        item.hbmpItem = hbmpItem
    if wID is not None:
        item.fMask |= MIIM_ID
        item.wID = wID
    if hSubMenu is not None:
        item.fMask |= MIIM_SUBMENU
        item.hSubMenu = hSubMenu
    return item


def LOWORD(value):
    return value & 0xFFFF
