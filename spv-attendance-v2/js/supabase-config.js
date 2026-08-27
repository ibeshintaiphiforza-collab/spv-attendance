// Konfigurasi Supabase untuk SPV Attendance
const SUPABASE_URL = 'https://crsfvucdnwurefjxtruk.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_UyaxKAlBRtbetob0CRKXPg_MRIqYNqC';

// Inisialisasi Klien Supabase
const _supabase = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);