// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{
    AppHandle, Emitter, Manager,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
};
use tauri_plugin_global_shortcut::{Code, Modifiers, ShortcutState};

struct WindowState {
    is_click_through: Mutex<bool>,
}

struct AppState {
    server_process: Mutex<Option<std::process::Child>>,
}

fn toggle_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            let _ = window.show();
            let _ = window.set_focus();
        }
    }
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    log::info!("Starting Mizune AI...");

    tauri::Builder::default()
        .manage(WindowState {
            is_click_through: Mutex::new(true), // Start as click-through
        })
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_shortcut("ctrl+m")
                .unwrap()
                .with_handler(|app, shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        if shortcut.matches(Modifiers::CONTROL, Code::KeyM) {
                            let state = app.state::<WindowState>();
                            let mut is_click_through = state.is_click_through.lock().unwrap();
                            *is_click_through = !*is_click_through;

                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.set_ignore_cursor_events(*is_click_through);
                                if !*is_click_through {
                                    let _ = window.set_focus();
                                }
                                let _ = window.emit("focus-mode-changed", *is_click_through);
                                log::info!("Toggled click-through mode: {}", *is_click_through);
                            }
                        }
                    }
                })
                .build(),
        )
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            log::info!("Setting up Tauri app...");

            // Automatically boot the Python Backend Server
            log::info!("Booting Python backend server silently...");
            #[cfg(target_os = "windows")]
            let child_process = {
                use std::os::windows::process::CommandExt;
                let root_dir = "C:\\Users\\rushi\\OneDrive\\Desktop\\my Ai";
                
                std::process::Command::new("python")
                    .arg("server.py")
                    .current_dir(root_dir)
                    .creation_flags(0x08000000)
                    .spawn()
                    .map_err(|e| log::error!("Failed to spawn python server: {}", e))
                    .ok()
            };
            #[cfg(not(target_os = "windows"))]
            let child_process = {
                std::process::Command::new(".venv/bin/python")
                    .current_dir("..")
                    .arg("server.py")
                    .spawn()
                    .ok()
            };
            
            app.manage(AppState {
                server_process: Mutex::new(child_process),
            });

            // Build tray menu
            let show_item = MenuItem::with_id(app, "show", "Show/Hide", true, None::<&str>)?;
            let settings_item = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
            let status_item = MenuItem::with_id(app, "status", "Status: Online", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

            let menu = Menu::with_items(app, &[&show_item, &settings_item, &status_item, &quit_item])?;

            // Build tray icon
            let _tray = TrayIconBuilder::with_id("main-tray")
                .menu(&menu)
                .tooltip("Mizune AI - Click to show/hide")
                .on_menu_event(|app, event| {
                    match event.id.as_ref() {
                        "show" => toggle_window(app),
                        "settings" => {
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                                let _ = window.emit("open-settings", ());
                            }
                        }
                        "status" => {
                            log::info!("Status: Online");
                        }
                        "quit" => {
                            log::info!("Quitting Mizune AI...");
                            let state = app.state::<AppState>();
                            let mut child_lock = state.server_process.lock().unwrap();
                            if let Some(mut child) = child_lock.take() {
                                let _ = child.kill();
                            }
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        toggle_window(app);
                    }
                })
                .build(app)?;

            log::info!("Tray icon built successfully");

            // Set up main window - use frameless for custom title bar
            if let Some(window) = app.get_webview_window("main") {
                log::info!("Main window configured");
                let _ = window.set_decorations(false);
                let _ = window.set_ignore_cursor_events(true); // Default to click-through
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                log::info!("Tauri Exit event fired. Killing python server...");
                let state = app_handle.state::<AppState>();
                let mut child_lock = state.server_process.lock().unwrap();
                if let Some(mut child) = child_lock.take() {
                    let _ = child.kill();
                }
            }
        });
}