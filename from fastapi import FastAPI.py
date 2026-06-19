from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
import asyncio

app = FastAPI()

# Permitir que el frontend se comunique con el backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

async def scrape_mercado_libre(query: str, country_domain: str = "com.ar"):
    """Busca productos en Mercado Libre"""
    url = f"https://listado.mercadolibre.{country_domain}/{query.replace(' ', '-')}"
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for item in soup.find_all('li', {'class': 'ui-search-layout__item'})[:5]:
                title = item.find('h2', {'class': 'ui-search-item__title'})
                price = item.find('span', {'class': 'andes-money-amount__fraction'})
                link = item.find('a', {'class': 'ui-search-link'})
                img = item.find('img', {'class': 'ui-search-result-image__element'})

                if title and price and link:
                    results.append({
                        "store": "Mercado Libre",
                        "name": title.text.strip(),
                        "price": float(price.text.replace('.', '').replace(',', '.')),
                        "link": link['href'],
                        "image": img['data-src'] if img.get('data-src') else img.get('src')
                    })
            return results
        except Exception as e:
            return [{"error": f"ML Error: {str(e)}"}]

@app.get("/search")
async def search_product(q: str):
    # Aquí puedes agregar más funciones de scraping para otras tiendas
    # y ejecutarlas en paralelo con asyncio.gather
    results = await asyncio.gather(
        scrape_mercado_libre(q, "com.ar") # Cambia el dominio a tu país
    )
    
    # Unir todas las listas de resultados y ordenar por precio
    flat_results = [item for sublist in results for item in sublist if "error" not in item]
    sorted_results = sorted(flat_results, key=lambda x: x['price'])
    
    return sorted_results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
