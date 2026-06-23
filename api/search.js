const ML_SITES = { "com.ar": "MLA", "com.mx": "MLM", "cl": "MLC", "com.co": "MCO" };

export default async function handler(req, res) {
    // Configuración de cabeceras CORS para permitir llamadas desde el frontend de GitHub Pages o local
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

    const clientId = process.env.ML_CLIENT_ID;
    const clientSecret = process.env.ML_CLIENT_SECRET;

    if (!clientId || !clientSecret) {
        return res.status(500).json({ error: 'Las credenciales de Mercado Libre (ML_CLIENT_ID o ML_CLIENT_SECRET) no están configuradas en las variables de entorno de Vercel.' });
    }

    try {
        // 1. Obtener el Access Token usando el flujo Client Credentials
        const tokenResponse = await fetch('https://api.mercadolibre.com/oauth/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            },
            body: new URLSearchParams({
                grant_type: 'client_credentials',
                client_id: clientId,
                client_secret: clientSecret
            })
        });

        if (!tokenResponse.ok) {
            const errData = await tokenResponse.json();
            console.error('Error obteniendo token:', errData);
            return res.status(tokenResponse.status).json({ error: 'No se pudo obtener el token de Mercado Libre', details: errData });
        }

        const tokenData = await tokenResponse.json();
        const accessToken = tokenData.access_token;

        // 2. Realizar la búsqueda en Mercado Libre usando el token obtenido
        const siteId = ML_SITES[country] || 'MLA';
        const searchUrl = `https://api.mercadolibre.com/sites/${siteId}/search?q=${encodeURIComponent(q)}&limit=40`;

        const searchResponse = await fetch(searchUrl, {
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });

        if (!searchResponse.ok) {
            const errData = await searchResponse.json();
            console.error('Error buscando:', errData);
            return res.status(searchResponse.status).json({ error: 'Error en la búsqueda de Mercado Libre', details: errData });
        }

        const searchData = await searchResponse.json();
        
        // Devolvemos el resultado al cliente
        return res.status(200).json(searchData);

    } catch (error) {
        console.error('Error en el servidor proxy:', error);
        return res.status(500).json({ error: 'Error interno del servidor', message: error.message });
    }
}
