// Both the Docker server and a configured Sites Worker use this read-only proxy.
export async function GET(req: Request, context: {params: Promise<{path:string[]}>}) {
  const base = process.env.ATLAS_DATA_URL;
  if (!base) return Response.json({error:'Service de données non configuré'}, {status:503});
  const {path} = await context.params;
  const value = path.join('/');
  if (!/^(manifest|cities|status|events|versions\/[\w-]{1,64}\/([a-z][a-z0-9-]{1,30}\.json|[a-z][a-z0-9-]{1,30}\/(transport|transactions)))$/.test(value)) {
    return Response.json({error:'Route inconnue'}, {status:404});
  }
  const query = new URL(req.url).search;
  if (query.length > 1024) return Response.json({error:'Requête trop longue'}, {status:400});
  try {
    const upstream = await fetch(base.replace(/\/$/,'')+'/api/v1/'+value+query, {
      signal:AbortSignal.timeout(15000), cache:'no-store',
      headers:process.env.ATLAS_DATA_READ_TOKEN ? {Authorization:'Bearer '+process.env.ATLAS_DATA_READ_TOKEN} : {},
    });
    if (!upstream.ok) return Response.json({error:'Version indisponible'}, {status:upstream.status});
    return new Response(upstream.body, {headers:{'Content-Type':'application/json','Cache-Control':value.startsWith('versions/')&&!value.endsWith('/transport')?'public, max-age=31536000, immutable':'no-store'}});
  } catch { return Response.json({error:'Service de données indisponible'}, {status:503}); }
}
