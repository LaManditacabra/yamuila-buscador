const ML_SITES = { "com.ar": "MLA", "com.mx": "MLM", "cl": "MLC", "com.co": "MCO" };

export default async function handler(req, res) {
    // Configuración de cabeceras CORS
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
    res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version');

    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    const { q, country } = req.query;

    if (!q) {
        return res.status(400).json({ error: 'Falta el parámetro de búsqueda q' });
    }

    try {
        const siteId = ML_SITES[country] || 'MLA';
        const searchUrl = `https://api.mercadolibre.com/sites/${siteId}/search?q=${encodeURIComponent(q)}&limit=40`;

        console.log('Realizando consulta a API de ML de forma anónima:', searchUrl);

        // Realizamos la petición HTTP simulando un navegador Chrome, sin enviar el token
        const searchResponse = await fetch(searchUrl, {
            headers: {
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'es-ES,es;q=0.9',
                'Cache-Control': 'no-cache'
            }
        });

        if (!searchResponse.ok) {
            const errData = await searchResponse.json();
            console.error('Error buscando de forma anónima:', errData);
            return res.status(searchResponse.status).json({ error: 'Error en la búsqueda anónima de Mercado Libre', details: errData });
        }

        const searchData = await searchResponse.json();
        
        // Devolvemos el resultado al cliente
        return res.status(200).json(searchData);

    } catch (error) {
        console.error('Error en el servidor proxy:', error);
        return res.status(500).json({ error: 'Error interno del servidor', message: error.message });
    }
}
