// Curated Database of 35+ DoH Resolvers with Browser CORS & Protocol Metadata
const DOH_PROVIDERS = [
  // ==================== ASIA-PACIFIC ====================
  {
    id: "alidns",
    name: "AliDNS (Alibaba Cloud)",
    flag: "🇨🇳",
    country: "China / SG",
    region: "asia",
    category: "general",
    cors: true,
    method: "json",
    doh: "https://dns.alidns.com/resolve",
    ips: ["223.5.5.5", "223.6.6.6"],
    desc: "Alibaba Cloud Anycast DNS - ultra-low latency in Indonesia and Asia-Pacific (JSON DoH)."
  },
  {
    id: "cloudflare",
    name: "Cloudflare Standard",
    flag: "🌐",
    country: "Global (JKT/SG)",
    region: "global",
    category: "general",
    cors: true,
    method: "post",
    doh: "https://cloudflare-dns.com/dns-query",
    ips: ["1.1.1.1", "1.0.0.1"],
    desc: "Cloudflare 1.1.1.1 - fastest Anycast network with Jakarta & Singapore PoPs."
  },
  {
    id: "cloudflare-security",
    name: "Cloudflare Security",
    flag: "🌐",
    country: "Global (JKT/SG)",
    region: "global",
    category: "security",
    cors: true,
    method: "post",
    doh: "https://security.cloudflare-dns.com/dns-query",
    ips: ["1.1.1.2", "1.0.0.2"],
    desc: "Cloudflare 1.1.1.2 - automated malware & phishing domain blocking."
  },
  {
    id: "cloudflare-family",
    name: "Cloudflare Family",
    flag: "🌐",
    country: "Global (JKT/SG)",
    region: "global",
    category: "family",
    cors: true,
    method: "post",
    doh: "https://family.cloudflare-dns.com/dns-query",
    ips: ["1.1.1.3", "1.0.0.3"],
    desc: "Cloudflare 1.1.1.3 - blocks malware and adult content."
  },
  {
    id: "google",
    name: "Google Public DNS",
    flag: "🌐",
    country: "Global (JKT/SG)",
    region: "global",
    category: "general",
    cors: true,
    method: "get_b64",
    doh: "https://dns.google/dns-query",
    ips: ["8.8.8.8", "8.8.4.4"],
    desc: "Google 8.8.8.8 - high-reliability global DNS with local Jakarta node (RFC 8484 GET)."
  },
  {
    id: "dns_sb",
    name: "DNS.SB",
    flag: "🇩🇪",
    country: "Germany",
    region: "europe",
    category: "privacy",
    cors: true,
    method: "post",
    doh: "https://doh.dns.sb/dns-query",
    ips: ["185.222.222.222", "45.11.45.11"],
    desc: "Privacy-first DNS with DNSSEC validation and no logging."
  },
  {
    id: "controld",
    name: "ControlD Unfiltered",
    flag: "🇨🇦",
    country: "Canada / Global",
    region: "global",
    category: "general",
    cors: true,
    method: "post",
    doh: "https://freedns.controld.com/p0",
    ips: ["76.76.2.0", "76.223.122.150"],
    desc: "ControlD P0 - high-speed unfiltered Anycast resolver."
  },
  {
    id: "controld-malware",
    name: "ControlD Malware",
    flag: "🇨🇦",
    country: "Canada / Global",
    region: "global",
    category: "security",
    cors: true,
    method: "post",
    doh: "https://freedns.controld.com/p1",
    ips: ["76.76.2.1", "76.223.122.151"],
    desc: "ControlD P1 - blocks malware and security threats."
  },
  {
    id: "controld-adblock",
    name: "ControlD Ads & Malware",
    flag: "🇨🇦",
    country: "Canada / Global",
    region: "global",
    category: "adblock",
    cors: true,
    method: "post",
    doh: "https://freedns.controld.com/p2",
    ips: ["76.76.2.2", "76.223.122.152"],
    desc: "ControlD P2 - blocks ads, tracking, and malware."
  },
  {
    id: "rethinkdns",
    name: "RethinkDNS",
    flag: "🇺🇸",
    country: "USA",
    region: "north_america",
    category: "security",
    cors: true,
    method: "post",
    doh: "https://sky.rethinkdns.com/dns-query",
    ips: ["104.21.83.62", "172.67.214.246"],
    desc: "Open source privacy and anti-censorship DNS."
  },

  // ==================== DESKTOP-NATIVE / NON-CORS PROVIDERS ====================
  {
    id: "adguard",
    name: "AdGuard Default",
    flag: "🇨🇾",
    country: "Cyprus / Global",
    region: "global",
    category: "adblock",
    cors: false,
    method: "post",
    doh: "https://dns.adguard-dns.com/dns-query",
    ips: ["94.140.14.14", "94.140.15.15"],
    desc: "AdGuard DNS (Desktop Only - Non-CORS on Web)."
  },
  {
    id: "quad9",
    name: "Quad9 (Malware Block)",
    flag: "🇨🇭",
    country: "Switzerland / Global",
    region: "global",
    category: "security",
    cors: false,
    method: "post",
    doh: "https://dns.quad9.net/dns-query",
    ips: ["9.9.9.9", "149.112.112.112"],
    desc: "Swiss non-profit threat blocking (Desktop Only - Non-CORS on Web)."
  },
  {
    id: "quad9-unfiltered",
    name: "Quad9 Unfiltered",
    flag: "🇨🇭",
    country: "Switzerland / Global",
    region: "global",
    category: "privacy",
    cors: false,
    method: "post",
    doh: "https://dns10.quad9.net/dns-query",
    ips: ["9.9.9.10", "149.112.112.10"],
    desc: "Quad9 Unfiltered (Desktop Only - Non-CORS on Web)."
  },
  {
    id: "nextdns",
    name: "NextDNS Public",
    flag: "🇺🇸",
    country: "USA / Global",
    region: "global",
    category: "privacy",
    cors: false,
    method: "post",
    doh: "https://dns.nextdns.io",
    ips: ["45.90.28.0", "45.90.30.0"],
    desc: "NextDNS Public (Desktop Only - Non-CORS on Web)."
  },
  {
    id: "opendns",
    name: "Cisco OpenDNS Home",
    flag: "🇺🇸",
    country: "USA",
    region: "north_america",
    category: "general",
    cors: false,
    method: "post",
    doh: "https://doh.opendns.com/dns-query",
    ips: ["208.67.222.222", "208.67.220.220"],
    desc: "Cisco OpenDNS (Desktop Only - Non-CORS on Web)."
  },
  {
    id: "cleanbrowsing",
    name: "CleanBrowsing Security",
    flag: "🇺🇸",
    country: "USA",
    region: "north_america",
    category: "security",
    cors: false,
    method: "post",
    doh: "https://doh.cleanbrowsing.org/doh/security-filter/",
    ips: ["185.228.168.9", "185.228.169.9"],
    desc: "CleanBrowsing Security (Desktop Only - Non-CORS on Web)."
  }
];

// Target Domain Datasets (Curated from Wide Note)
const DOMAIN_DATASETS = {
  indonesia: {
    name: "🇮🇩 Indonesia Regional (IIX / OpenIXP)",
    domains: [
      "bca.co.id",
      "klikbca.com",
      "bankmandiri.co.id",
      "tokopedia.com",
      "shopee.co.id",
      "gojek.com",
      "detik.com",
      "kompas.com",
      "kemkes.go.id",
      "pajak.go.id",
      "ui.ac.id",
      "pandi.id"
    ]
  },
  global: {
    name: "🌐 Global Popular (.com, .net, .org)",
    domains: [
      "google.com",
      "youtube.com",
      "facebook.com",
      "chatgpt.com",
      "x.com",
      "wikipedia.org",
      "reddit.com",
      "amazon.com",
      "github.com",
      "netflix.com"
    ]
  }
};
