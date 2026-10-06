# LeadForge RJ — Zero Custo

CRM para prospecção de pequenos negócios, sem Google Cloud e sem chave de API paga. A descoberta usa OpenStreetMap/Overpass; o serviço público é compartilhado, portanto o app faz consultas pequenas e sem paralelismo.

## Variáveis Vercel
ADMIN_PASSWORD
SESSION_SECRET
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_TABLE=leads
OVERPASS_URL=https://overpass-api.de/api/interpreter

## Supabase
Execute `supabase.sql` no SQL Editor. Depois coloque URL e service role key nas Environment Variables da Vercel.

## Importante
OSM não garante telefone, site, Instagram, fotos ou avaliações em todos os estabelecimentos. O CRM prioriza sem site + telefone para prospecção.
