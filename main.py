import asyncio
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright
from io import StringIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe
import os
from dotenv import load_dotenv

# Cargar las variables del archivo .env al entorno del sistema
load_dotenv()
# ================= CONFIGURACIÓN SEGURA =================
CONFIG = {
    "SHEET_ID": os.getenv("SHEET_ID"),
    "CNBV_USER": os.getenv("CNBV_USER"),
    "CNBV_PASS": os.getenv("CNBV_PASS"),
    "EMAIL_USER": os.getenv("EMAIL_USER"),
    "EMAIL_PASS": os.getenv("EMAIL_PASS"),
    "EMAIL_DEST": os.getenv("EMAIL_DEST"),
    "URL_LOGIN": os.getenv("URL_LOGIN"),
    "URL_CONSULTA": os.getenv("URL_CONSULTA")
}

URLS = {
    "LOGIN": CONFIG['URL_LOGIN'],
    "CONSULTA": CONFIG['URL_CONSULTA'],
    "SHEET_BASE": f"https://docs.google.com/spreadsheets/d/{CONFIG['SHEET_ID']}"
}

info_credentials_gcp = {
    "type": os.getenv("GCP_TYPE"),
    "project_id": os.getenv("GCP_PROJECT_ID"),
    "private_key_id": os.getenv("GCP_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GCP_PRIVATE_KEY"),
    "client_email": os.getenv("GCP_CLIENT_EMAIL"),
    "client_id": os.getenv("GCP_CLIENT_ID"),
    "auth_uri": os.getenv("GCP_AUTH_URI"),
    "token_uri": os.getenv("GCP_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GCP_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("GCP_CLIENT_X509_CERT_URL"),
    "universe_domain": os.getenv("GCP_UNIVERSE_DOMAIN"),
}

# ================= CONEXIÓN GOOGLE SHEETS =================
def get_gspread_client():
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(info_credentials_gcp, scope)
    
    return gspread.authorize(creds)

gc = get_gspread_client()

# ================= NOTIFICACIONES =================

def notificar_novedades(nuevos_registros):
    """Escribe en la hoja Novedades y opcionalmente envía correo"""
    try:
        spreadsheet = gc.open_by_key(CONFIG['SHEET_ID'])
        worksheet = spreadsheet.worksheet('Novedades')
        
        # Limpiamos y escribimos
        worksheet.clear()
        set_with_dataframe(worksheet, nuevos_registros)
        print("[GSPREAD] Hoja 'Novedades' actualizada.")
        
    except Exception as e:
        print(f"[ERROR GSPREAD] Al actualizar novedades: {e}")

# ================= LÓGICA DE DATOS =================
def procesar_datos(df_nuevo):
    """
    Compara y guarda. Optimizado para append en lugar de overwrite total.
    """
    if df_nuevo.empty:
        print("[INFO] No se encontraron datos en el escaneo.")
        return

    try:
        spreadsheet = gc.open_by_key(CONFIG['SHEET_ID'])
        worksheet = spreadsheet.worksheet("Resultados")
        
        # Obtenemos solo la columna de Folios existentes para comparar (más rápido que bajar todo)
        # Asumiendo que 'Folio' está en la columna A (índice 1). Ajustar si es diferente.
        # Si no, bajamos todo el dataframe como hacías antes:
        datos_existentes = worksheet.get_all_records()
        df_existente = pd.DataFrame(datos_existentes)
        
        col_id = "Folio"
        nuevos_reales = pd.DataFrame()

        if not df_existente.empty and col_id in df_existente.columns and col_id in df_nuevo.columns:
            # Convertir a string para asegurar match
            existentes_ids = set(df_existente[col_id].astype(str))
            # Filtramos lo que NO esté en existentes
            nuevos_reales = df_nuevo[~df_nuevo[col_id].astype(str).isin(existentes_ids)]
        else:
            nuevos_reales = df_nuevo

        if not nuevos_reales.empty:
            print(f"[DATOS] 💡 Se encontraron {len(nuevos_reales)} registros realmente nuevos.")
            
            # Append eficiente: Escribimos al final de la hoja existente
            # include_column_header=False para no repetir títulos
            row_to_start = len(df_existente) + 2 # +1 por header, +1 para la siguiente fila vacía
            set_with_dataframe(worksheet, nuevos_reales, row=row_to_start, include_column_header=False)
            
            print(f"[EXITO] ✅ Datos guardados.")
            
            # Notificar
            notificar_novedades(nuevos_reales)
        else:
            print("[INFO] zzz Los datos escaneados ya existen en la base.")

    except Exception as e:
        print(f"[ERROR PROCESAMIENTO] {e}")

# ================= AUTOMATIZACIÓN (PLAYWRIGHT) =================
async def extraer_datos_web():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando escaneo web...")
    data_list = []
    
    # Es necesario importar StringIO arriba: from io import StringIO

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # --- LOGIN ---
            await page.goto(URLS["LOGIN"])
            await page.fill("#ctl00_DefaultPlaceholder_textBoxUser", CONFIG["CNBV_USER"])
            await page.fill("#ctl00_DefaultPlaceholder_textBoxPassword", CONFIG["CNBV_PASS"])
            
            async with page.expect_navigation():
                await page.click("input[type='submit']")

            # --- NAVEGACIÓN A CONSULTA ---
            await page.goto(URLS["CONSULTA"])
            
            areas = ['Hacendario', 'Judicial', 'Aseguramiento', 'Operaciones Ilícitas']
            
            for area in areas:
                print(f"--- Consultando: {area} ---")
                try:
                    # 1. Selecciones
                    await page.select_option("#ctl00_DefaultPlaceholder_ComboBoxAreas", label=area)
                    await page.select_option("#ctl00_DefaultPlaceholder_ComboBoxTipoRespuesta", label="Rechazos")
                    
                    # 2. ESTRATEGIA ANTI-DATOS FANTASMA
                    # Creamos una promesa que espera a que haya una respuesta de red tras el click.
                    # Esto es vital en ASP.NET para asegurar que el servidor respondió antes de leer la tabla.
                    async with page.expect_response(lambda response: response.status == 200, timeout=10000) as response_info:
                        await page.get_by_role("button", name='Consultar').click()
                    
                    await asyncio.sleep(0.5)

                    # 3. Esperar tabla
                    try:
                        await page.wait_for_selector("#ctl00_DefaultPlaceholder_GridResult", state="visible", timeout=8000)
                    except Exception:
                        print(f"   [WARN] No hay tabla para {area} (Timeout o sin datos).")
                        continue 

                    # 4. Validar Caption (Tu código corregido)
                    locator = page.locator("#ctl00_DefaultPlaceholder_GridResult caption div b")
                    
                    # Verifica si existe el caption antes de leer (para evitar error si la tabla cargó raro)
                    if await locator.count() > 0:
                        caption_info = await locator.inner_text()
                        if '0 requerimiento(s)' in caption_info.strip().lower():
                            print(f"   [INFO] 0 Requerimientos para {area}")
                            continue
                    
                    # 5. Extracción
                    html = await page.inner_html("#ctl00_DefaultPlaceholder_GridResult")
                    
                    # Parseo
                    # Nota: Read_html devuelve una lista, tomamos el [0]
                    dfs = pd.read_html(StringIO(f"<table>{html}</table>"))[0]
                    dfs['Area'] = area 
                    
                    # Limpieza
                    cols_to_drop = [c for c in ["Unnamed: 0", "Comentario Rechazo"] if c in dfs.columns]
                    dfs = dfs.drop(columns=cols_to_drop)
                    
                    data_list.append(dfs)
                    print(f"   [OK] {len(dfs)} registros extraídos.")
                    
                except Exception as e_area:
                    print(f"   [ERROR AREA] Fallo procesando {area}: {e_area}")
                    continue

        except Exception as e:
            print(f"[ERROR CRÍTICO] Fallo en navegación: {e}")
            await page.screenshot(path="error_login.png")
        
        finally:
            await browser.close()
    
    if data_list:
        return pd.concat(data_list, ignore_index=True)
    return pd.DataFrame()

# ================= BUCLE PRINCIPAL =================
async def main_loop():
    print("🤖 Bot iniciado. Ctrl+C para detener.")
    try:
        df_resultado = await extraer_datos_web()
        
        if not df_resultado.empty:
            # Ejecutar procesamiento síncrono
            procesar_datos(df_resultado)
        
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por usuario.")
    except Exception as e:
        print(f"[ERROR GLOBAL] {e}")

if __name__ == "__main__":
    asyncio.run(main_loop())