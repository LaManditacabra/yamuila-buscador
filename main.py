import asyncio
import sys
import logging
import urllib.parse
import re
import random
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser
# Configuración de event loop para Windows antes de cualquier importación de Playwright o FastAPI
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Intentar importar la función 'stealth' de forma robusta
try:
    from playwright_stealth.stealth import stealth as apply_stealth_function
except ImportError:
    try:
# --- Bloque de importación y configuración inicial ---
# Se mantiene la compatibilidad con diferentes versiones de playwright-stealth
        from playwright_stealth import stealth as apply_stealth_function
    except ImportError:
        apply_stealth_function = None

app = FastAPI(title="Yamuila Buscador API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}

def parse_price(price_text: str) -> float:
    """
    Limpia y convierte una cadena de precio a float, manejando diversos separadores.
    """
    if not price_text:
        return 0.0
    
# --- Bloque de procesamiento de precios ---
# Se asegura la limpieza de caracteres no numéricos y manejo de decimales
    # Limpieza total: quitar símbolos de moneda, espacios y letras
    cleaned = re.sub(r'[^\d.,]', '', price_text)
    if not cleaned: return 0.0

    last_dot = cleaned.rfind('.')
    last_comma = cleaned.rfind(',')
    
    try:
        # Si tiene ambos (1.234,56), el último es el decimal
        if last_dot != -1 and last_comma != -1:
            if last_comma > last_dot:
                return float(cleaned.replace('.', '').replace(',', '.'))
            return float(cleaned.replace(',', ''))
        
        # Si solo tiene uno, verificamos si son miles (ej: 16.000) o decimales (ej: 16.50)
        separator_idx = max(last_dot, last_comma)
        if separator_idx != -1:
            decimals = cleaned[separator_idx+1:]
            # Si tiene 3 dígitos después, es un punto de miles (16.000 -> 16000)
            if len(decimals) == 3:
                return float(cleaned.replace('.', '').replace(',', ''))
            return float(cleaned.replace(',', '.'))
            
        else:
            return float(cleaned.replace(',', '.'))
    except Exception:
        return 0.0

# Tasas de conversión aproximadas de USD a la moneda local de cada país
EXCHANGE_RATES = {
    "ARS": 1250.0,  # 1 USD = 1250 ARS (Valor aproximado para comparación realista en Argentina)
    "MXN": 18.0,    # 1 USD = 18 MXN
    "CLP": 930.0,   # 1 USD = 930 CLP
    "COP": 4100.0   # 1 USD = 4100 COP
}

def parse_price_and_currency(price_text: str, target_currency: str) -> tuple[float, str]:
    if not price_text:
        return 0.0, target_currency

    cleaned = price_text.upper()
    detected_currency = target_currency

    # Detectar monedas comunes a partir de su texto
    if "ARS" in cleaned:
        detected_currency = "ARS"
    elif "MXN" in cleaned or "MX$" in cleaned:
        detected_currency = "MXN"
    elif "COP" in cleaned:
        detected_currency = "COP"
    elif "CLP" in cleaned or "CL$" in cleaned:
        detected_currency = "CLP"
    elif "US$" in cleaned or "USD" in cleaned:
        detected_currency = "USD"
    elif "EUR" in cleaned or "€" in cleaned:
        detected_currency = "EUR"

    # Extraer el valor numérico
    cleaned_num = re.sub(r'[^\d.,]', '', price_text)
    price_val = parse_price(cleaned_num)

    # Lógica heurística de desambiguación para Amazon
    # Si contiene "$" pero no se especificó otra moneda explícitamente:
    if "$" in cleaned and not any(m in cleaned for m in ["ARS", "MXN", "CLP", "COP", "US"]):
        if price_val < 1000:
            # En Amazon, un precio menor a 1000 sin especificar la moneda local suele ser USD
            detected_currency = "USD"
        else:
            # Si es mayor a 1000 y el target es ARS, CLP o COP, asumimos que ya está en la moneda local
            detected_currency = target_currency

    return price_val, detected_currency

async def scrape_store(browser: Browser, url: str, store_name: str, item_selector: str, title_selector: str, price_selector: str, link_selector: str, img_selector: str, target_currency: str = "ARS"):
    # Creamos un contexto con User-Agent para mayor realismo
    context = await browser.new_context(
        user_agent=HEADERS["User-Agent"],
        viewport={'width': 1280, 'height': 720},
        extra_http_headers={
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }
    )
    page = await context.new_page()
    
# --- Bloque de navegación y sigilo ---
# Aplicación de stealth para evitar bloqueos de bots en Amazon/ML
    try:
        if apply_stealth_function:
            await apply_stealth_function(page)
    except Exception as e:
        logging.debug(f"Error al aplicar stealth en {store_name}: {e}")

    results = []
    try:
        # Simulación humana: visita la home primero para obtener cookies de sesión
        if "mercadolibre" in url.lower():
            try:
                parsed = urllib.parse.urlparse(url)
                home_url = f"{parsed.scheme}://{parsed.netloc}/"
                await page.goto(home_url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(random.uniform(1, 3))
            except Exception:
                pass

        logging.info(f"Buscando en {store_name}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Scroll dinámico optimizado: limitado a 3 saltos para evitar timeouts
        last_height = await page.evaluate("document.body.scrollHeight")
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            # Reducimos el tiempo de espera para que la respuesta sea más rápida
            await asyncio.sleep(random.uniform(0.8, 1.2)) 
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        try:
            await page.wait_for_selector(item_selector, timeout=15000)
        except Exception:
            return []
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        items = soup.select(item_selector)[:20]

        for item in items:
            title_elem = item.select_one(title_selector) or item.select_one("h2, h3")
            price_elem = item.select_one(price_selector)
            link_elem = item.select_one(link_selector) or item.select_one("a")
            img_elem = item.select_one(img_selector)

            if title_elem and price_elem and link_elem:
                # Extraer texto del precio (de a-offscreen para Amazon si se usa span.a-price)
                if store_name == "Amazon" and price_selector == "span.a-price":
                    offscreen = price_elem.select_one("span.a-offscreen")
                    price_text = offscreen.get_text().strip() if offscreen else price_elem.get_text(separator='').strip()
                else:
                    price_text = price_elem.get_text(separator='').strip()

                price_val, item_currency = parse_price_and_currency(price_text, target_currency)
                
                # Conversión de monedas
                converted_price = price_val
                if item_currency == "USD" and target_currency != "USD":
                    rate = EXCHANGE_RATES.get(target_currency, 1.0)
                    converted_price = price_val * rate

                href = link_elem.get('href')
                if price_val > 0 and href:
                    img_url = ""
                    if img_elem:
                        # Búsqueda exhaustiva en atributos comunes de lazy loading (ML y Amazon)
                        attrs = ['data-src', 'data-lazy-src', 'src', 'srcset', 'data-original']
                        for attr in attrs:
                            val = img_elem.get(attr)
                            if val and "data:image" not in val and "placeholder" not in val.lower():
                                # srcset puede contener varias URLs, tomamos la primera
                                img_url = val.split(' ')[0]
                                break

                    results.append({
                        "store": store_name,
                        "name": title_elem.get_text().strip()[:100],
                        "price": round(converted_price, 2),
                        "currency": target_currency,
                        "original_price": price_val,
                        "original_currency": item_currency,
                        "link": urllib.parse.urljoin(url, href).split('?')[0],
                        "image": img_url
                    })
        return results
    except Exception as e:
        logging.error(f"Error en {store_name}: {str(e)}")
        return []
    finally:
# --- Bloque de cierre de recursos ---
# Cerramos la página y el contexto explícitamente para liberar memoria
        await page.close()
        await context.close()

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/search")
async def search_product(q: str = Query(..., min_length=2), country: str = "com.ar", page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    logging.info(f"Iniciando búsqueda para '{q}' en {country}...")
    
    amazon_domains = {"com.mx": "com.mx", "com.co": "com", "cl": "com", "com.ar": "com"}
# --- Bloque de configuración de búsqueda ---
# Mapeo de dominios de Amazon según el país seleccionado
    amz_domain = amazon_domains.get(country, "com")

    country_currencies = {
        "com.ar": "ARS",
        "com.mx": "MXN",
        "cl": "CLP",
        "com.co": "COP"
    }
    local_currency = country_currencies.get(country, "ARS")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,720"
            ]
        )
        
        tasks = [
            scrape_store(
                browser,
                f"https://listado.mercadolibre.{country}/{q.replace(' ', '-')}",
                "Mercado Libre",
                "li.ui-search-layout__item",
                "h2.ui-search-item__title",
                "span.andes-money-amount__fraction", 
                "a.ui-search-link",
                "img.ui-search-result-image__element",
                target_currency=local_currency
            ),
            scrape_store(
                browser,
                f"https://www.amazon.{amz_domain}/s?k={q.replace(' ', '+')}",
                "Amazon",
                "div[data-component-type='s-search-result'], .s-result-item[data-asin]",
                "h2 a span, .a-text-normal, .a-size-medium",
                "span.a-price",
                "h2 a, .a-link-normal, a[href*='/dp/']",
                "img.s-image",
                target_currency=local_currency
            )
        ]
        
        all_results = await asyncio.gather(*tasks)
        await browser.close()

        flat_results = [item for sublist in all_results for item in sublist]
        sorted_results = sorted(flat_results, key=lambda x: x['price'])
        
        # Aplicar paginación
        total_results = len(sorted_results)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_results = sorted_results[start_index:end_index]
        
        return {"total_results": total_results, "page": page, "page_size": page_size, "items": paginated_results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, loop="asyncio")
