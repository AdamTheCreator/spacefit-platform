/* Contacts — sample company + contact directory data */

// Sector color palette for monogram fallbacks
export const sectorColor: Record<string, string> = {
  'Fast Casual': '#FF8A3D',
  'QSR': '#E5B85C',
  'Coffee': '#8A6417',
  'Fitness': '#3A5BA0',
  'Grocery': '#2F7A3B',
  'Beauty': '#C25E1F',
  'Apparel': '#0F1B2D',
  'Specialty Food': '#FF8A3D',
  'Better Burger': '#C25E1F',
  'Eyewear': '#3A5BA0',
  'Home': '#8A6417',
  'Health': '#2F7A3B',
};

export interface Company {
  id: string;
  name: string;
  sector: string;
  subsector: string;
  us_locations: number;
  is_expanding: boolean | null;
  target_markets: string[];
  sf_min: number;
  sf_max: number;
  website: string;
  enriched_days: number;
  logo_bg: string;
  logo_text: string;
  notes: string;
}

export type VerificationStatus = 'verified' | 'unverified' | 'stale' | 'bounced';
export type ContactSource = 'apollo' | 'linkedin' | 'costar_import' | 'manual';

export interface Contact {
  id: string;
  company_id: string;
  first: string;
  last: string;
  role: string;
  email: string | null;
  phone: string | null;
  verif: VerificationStatus;
  last_verified_days: number | null;
  last_contacted_days: number | null;
  last_reply_days: number | null;
  source: ContactSource;
  linkedin: boolean;
  notes: string;
}

export type InteractionType = 'meeting' | 'note' | 'enrich' | 'email_in' | 'email_out';

export interface Interaction {
  id: string;
  contact_id: string;
  type: InteractionType;
  when_days: number;
  who: string;
  title?: string;
  summary: string;
}

export const companies: Company[] = [
  { id:'co_shake',   name:'Shake Shack',        sector:'Fast Casual',   subsector:'Better Burger', us_locations:298, is_expanding:true,  target_markets:['NY','NJ','CT','PA','MA'], sf_min:2200, sf_max:3200, website:'shakeshack.com', enriched_days:12, logo_bg:'#0F9548', logo_text:'Sh', notes:'Committee meets Thurs. Prefers endcaps w/ patio.' },
  { id:'co_sweet',   name:'Sweetgreen',         sector:'Fast Casual',   subsector:'Salad',         us_locations:226, is_expanding:true,  target_markets:['NY','NJ','CT','PA','VA','DC'], sf_min:2000, sf_max:3000, website:'sweetgreen.com', enriched_days:18, logo_bg:'#3F6A45', logo_text:'sg', notes:'Heavy Westchester cluster; prefers street-front.' },
  { id:'co_cava',    name:'Cava',               sector:'Fast Casual',   subsector:'Mediterranean', us_locations:352, is_expanding:true,  target_markets:['Northeast','Mid-Atl','Southeast','TX'], sf_min:2400, sf_max:3200, website:'cava.com', enriched_days:6, logo_bg:'#F7C35A', logo_text:'C', notes:'' },
  { id:'co_chip',    name:'Chipotle',           sector:'Fast Casual',   subsector:'Mexican',       us_locations:3510, is_expanding:true, target_markets:['Nationwide'], sf_min:2200, sf_max:2800, website:'chipotle.com', enriched_days:4, logo_bg:'#A81612', logo_text:'C', notes:'Chipotlane + endcap strongly preferred.' },
  { id:'co_honey',   name:'Honeygrow',          sector:'Fast Casual',   subsector:'Asian',         us_locations:42,  is_expanding:true,  target_markets:['PA','NJ','NY','MD','DC','VA'], sf_min:1800, sf_max:2600, website:'honeygrow.com', enriched_days:34, logo_bg:'#F4AE1F', logo_text:'hg', notes:'' },
  { id:'co_jersey',  name:'Jersey Mike\u2019s', sector:'Fast Casual',   subsector:'Sandwich',      us_locations:2860, is_expanding:true, target_markets:['Nationwide'], sf_min:1400, sf_max:1800, website:'jerseymikes.com', enriched_days:22, logo_bg:'#004A8F', logo_text:'JM', notes:'' },
  { id:'co_cava_b',  name:'Dig Inn',            sector:'Fast Casual',   subsector:'Seasonal',      us_locations:28,  is_expanding:null,  target_markets:['NY','NJ','CT'], sf_min:2000, sf_max:2800, website:'diginn.com', enriched_days:110, logo_bg:'#2F5E3A', logo_text:'D', notes:'Exec. shakeup Q1; expansion paused.' },
  { id:'co_panera',  name:'Panera Bread',       sector:'Fast Casual',   subsector:'Bakery-Cafe',   us_locations:2140, is_expanding:false, target_markets:['Nationwide'], sf_min:3800, sf_max:4800, website:'panerabread.com', enriched_days:48, logo_bg:'#6E5236', logo_text:'P', notes:'Net-closing stores in secondary mkts.' },
  { id:'co_cane',    name:'Raising Cane\u2019s', sector:'QSR',          subsector:'Chicken',       us_locations:810, is_expanding:true,  target_markets:['Nationwide'], sf_min:3200, sf_max:4200, website:'raisingcanes.com', enriched_days:14, logo_bg:'#CF202E', logo_text:'RC', notes:'' },
  { id:'co_wingst',  name:'Wingstop',           sector:'QSR',           subsector:'Chicken',       us_locations:2060, is_expanding:true, target_markets:['Nationwide'], sf_min:1500, sf_max:2000, website:'wingstop.com', enriched_days:28, logo_bg:'#B90E0A', logo_text:'W', notes:'' },
  { id:'co_chick',   name:'Chick-fil-A',        sector:'QSR',           subsector:'Chicken',       us_locations:3059, is_expanding:true, target_markets:['Nationwide'], sf_min:4500, sf_max:5200, website:'chick-fil-a.com', enriched_days:60, logo_bg:'#DD0031', logo_text:'C', notes:'Corporate only, franchisees rare in NE.' },
  { id:'co_first',   name:'First Watch',        sector:'Fast Casual',   subsector:'Breakfast',     us_locations:548, is_expanding:true,  target_markets:['Nationwide'], sf_min:3600, sf_max:4800, website:'firstwatch.com', enriched_days:9,  logo_bg:'#F58320', logo_text:'FW', notes:'' },
  { id:'co_joe',     name:'Joe & The Juice',    sector:'Coffee',        subsector:'Juice+Coffee',  us_locations:110, is_expanding:true,  target_markets:['NY','CA','IL','MA'], sf_min:900, sf_max:1400, website:'joejuice.com', enriched_days:7, logo_bg:'#EE5F9E', logo_text:'J', notes:'' },
  { id:'co_blank',   name:'Blank Street',       sector:'Coffee',        subsector:'Third Wave',    us_locations:75,  is_expanding:true,  target_markets:['NY','Boston','DC','London'], sf_min:450, sf_max:900, website:'blankstreet.com', enriched_days:20, logo_bg:'#6B8E4E', logo_text:'b', notes:'Focused on high-traffic urban right now.' },
  { id:'co_bluebot', name:'Blue Bottle Coffee', sector:'Coffee',        subsector:'Specialty',     us_locations:102, is_expanding:true,  target_markets:['NY','NJ','MA','CA'], sf_min:1200, sf_max:2200, website:'bluebottlecoffee.com', enriched_days:38, logo_bg:'#008BCD', logo_text:'Bb', notes:'' },
  { id:'co_stumpt',  name:'Stumptown',          sector:'Coffee',        subsector:'Specialty',     us_locations:13,  is_expanding:false, target_markets:['NY','OR','LA'], sf_min:900, sf_max:1800, website:'stumptowncoffee.com', enriched_days:160, logo_bg:'#8A2A23', logo_text:'S', notes:'Stale: parent restructured 2024.' },
  { id:'co_jeni',    name:'Jeni\u2019s Ice Cream', sector:'Specialty Food', subsector:'Ice Cream', us_locations:74,  is_expanding:true,  target_markets:['NY','OH','TX','IL','CO'], sf_min:900, sf_max:1400, website:'jenis.com', enriched_days:21, logo_bg:'#EDA0BD', logo_text:'J', notes:'' },
  { id:'co_levain',  name:'Levain Bakery',      sector:'Specialty Food', subsector:'Bakery',       us_locations:11,  is_expanding:true,  target_markets:['NY','CT','MA','DC','CA'], sf_min:1200, sf_max:1800, website:'levainbakery.com', enriched_days:40, logo_bg:'#6B2C10', logo_text:'Lv', notes:'' },
  { id:'co_vansl',   name:'Van Leeuwen',        sector:'Specialty Food', subsector:'Ice Cream',    us_locations:48,  is_expanding:true,  target_markets:['NY','NJ','CA','TX'], sf_min:800, sf_max:1200, website:'vanleeuwenicecream.com', enriched_days:70, logo_bg:'#4A6742', logo_text:'VL', notes:'' },
  { id:'co_saltgr',  name:'Salt & Straw',       sector:'Specialty Food', subsector:'Ice Cream',    us_locations:36,  is_expanding:true,  target_markets:['OR','WA','CA','NY','FL'], sf_min:1000, sf_max:1500, website:'saltandstraw.com', enriched_days:55, logo_bg:'#F4D3A2', logo_text:'SS', notes:'' },
  { id:'co_warby',   name:'Warby Parker',       sector:'Eyewear',       subsector:'DTC',           us_locations:270, is_expanding:true,  target_markets:['Nationwide'], sf_min:1200, sf_max:2200, website:'warbyparker.com', enriched_days:15, logo_bg:'#0F1B2D', logo_text:'W', notes:'' },
  { id:'co_aloyoga', name:'Alo Yoga',           sector:'Apparel',       subsector:'Athleisure',    us_locations:93,  is_expanding:true,  target_markets:['Nationwide'], sf_min:3000, sf_max:5000, website:'aloyoga.com', enriched_days:46, logo_bg:'#1F1F1F', logo_text:'alo', notes:'' },
  { id:'co_lulu',    name:'Lululemon',          sector:'Apparel',       subsector:'Athleisure',    us_locations:370, is_expanding:true,  target_markets:['Nationwide'], sf_min:3000, sf_max:4500, website:'lululemon.com', enriched_days:33, logo_bg:'#C8102E', logo_text:'L', notes:'' },
  { id:'co_sephora', name:'Sephora',            sector:'Beauty',        subsector:'Multi-brand',   us_locations:615, is_expanding:true,  target_markets:['Nationwide'], sf_min:4500, sf_max:7500, website:'sephora.com', enriched_days:19, logo_bg:'#0F1B2D', logo_text:'S', notes:'' },
  { id:'co_glossier',name:'Glossier',           sector:'Beauty',        subsector:'DTC',           us_locations:14,  is_expanding:true,  target_markets:['NY','CA','IL','MA','TX'], sf_min:1800, sf_max:3000, website:'glossier.com', enriched_days:62, logo_bg:'#FFD5C8', logo_text:'G', notes:'' },
  { id:'co_bark',    name:'Barry\u2019s',       sector:'Fitness',       subsector:'Bootcamp',      us_locations:76,  is_expanding:true,  target_markets:['NY','NJ','CA','IL'], sf_min:4000, sf_max:5500, website:'barrys.com', enriched_days:52, logo_bg:'#0F1B2D', logo_text:'B', notes:'' },
  { id:'co_solid',   name:'SolidCore',          sector:'Fitness',       subsector:'Pilates',       us_locations:120, is_expanding:true,  target_markets:['Nationwide'], sf_min:2200, sf_max:3200, website:'solidcore.co', enriched_days:11, logo_bg:'#0F1B2D', logo_text:'s', notes:'' },
  { id:'co_orange',  name:'Orangetheory',       sector:'Fitness',       subsector:'HIIT',          us_locations:1450, is_expanding:false, target_markets:['Nationwide'], sf_min:2500, sf_max:3500, website:'orangetheoryfitness.com', enriched_days:130, logo_bg:'#F16522', logo_text:'OT', notes:'Stale: franchisee contact may have changed.' },
  { id:'co_erewhon', name:'Erewhon',            sector:'Grocery',       subsector:'Specialty',     us_locations:10,  is_expanding:true,  target_markets:['CA','NY','FL'], sf_min:8000, sf_max:15000, website:'erewhonmarket.com', enriched_days:42, logo_bg:'#2A4D29', logo_text:'E', notes:'' },
  { id:'co_onemed',  name:'One Medical',        sector:'Health',        subsector:'Primary Care',  us_locations:220, is_expanding:true,  target_markets:['Nationwide'], sf_min:3500, sf_max:6000, website:'onemedical.com', enriched_days:25, logo_bg:'#145DA0', logo_text:'1M', notes:'' },
  { id:'co_westel',  name:'West Elm',           sector:'Home',          subsector:'Furniture',     us_locations:135, is_expanding:false, target_markets:['Nationwide'], sf_min:8000, sf_max:14000, website:'westelm.com', enriched_days:95, logo_bg:'#4E4B3B', logo_text:'we', notes:'' },
];

export const contacts: Contact[] = [
  { id:'ct_britt',   company_id:'co_shake',  first:'Brittany', last:'Cho',     role:'Director of Real Estate', email:'bcho@shakeshack.com',       phone:'(212) 555-0177', verif:'verified',   last_verified_days:6,  last_contacted_days:2,  last_reply_days:0,  source:'apollo',        linkedin:true,  notes:'Prefers warm intros; worked at Dig Inn previously.' },
  { id:'ct_kev_s',   company_id:'co_shake',  first:'Kevin',    last:'Mara',    role:'Sr. Real Estate Manager', email:'kmara@shakeshack.com',      phone:'(212) 555-0198', verif:'verified',   last_verified_days:15, last_contacted_days:42, last_reply_days:45, source:'costar_import', linkedin:true,  notes:'' },
  { id:'ct_dara',    company_id:'co_shake',  first:'Dara',     last:'Alam',    role:'Real Estate Analyst',    email:'dalam@shakeshack.com',       phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'apollo',     linkedin:true,  notes:'' },
  { id:'ct_marcus',  company_id:'co_sweet',  first:'Marcus',   last:'Reyna',   role:'VP Expansion',           email:'marcus.r@sweetgreen.com',   phone:'(347) 555-0132', verif:'verified',   last_verified_days:12, last_contacted_days:5, last_reply_days:null, source:'apollo',        linkedin:true,  notes:'' },
  { id:'ct_kat_sg',  company_id:'co_sweet',  first:'Katrina',  last:'Lu',      role:'Director of RE, Northeast', email:'klu@sweetgreen.com',       phone:'(347) 555-0188', verif:'verified',   last_verified_days:30, last_contacted_days:88, last_reply_days:90, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_jomi',    company_id:'co_sweet',  first:'Joshua',   last:'Mitchell',role:'Real Estate Associate',  email:'jmitchell@sweetgreen.com',  phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'costar_import',linkedin:false, notes:'' },
  { id:'ct_diane',   company_id:'co_cava',   first:'Diane',    last:'Okafor',  role:'Head of Sites',          email:'diane@cava.com',             phone:'(240) 555-0108', verif:'verified',   last_verified_days:3,  last_contacted_days:7, last_reply_days:null, source:'apollo',        linkedin:true,  notes:'' },
  { id:'ct_jared',   company_id:'co_cava',   first:'Jared',    last:'Finkel',  role:'Real Estate, Northeast', email:'jfinkel@cava.com',           phone:'(240) 555-0154', verif:'verified',   last_verified_days:22, last_contacted_days:60, last_reply_days:null, source:'linkedin',   linkedin:true,  notes:'' },
  { id:'ct_ben',     company_id:'co_chip',   first:'Ben',      last:'Trilling',role:'Real Estate Manager',    email:'btrilling@chipotle.com',     phone:'(714) 555-0117', verif:'verified',   last_verified_days:4,  last_contacted_days:2, last_reply_days:null, source:'apollo',        linkedin:true,  notes:'' },
  { id:'ct_anna_ch', company_id:'co_chip',   first:'Anna',     last:'Voss',    role:'Director, Development',  email:'avoss@chipotle.com',         phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_rh_chip', company_id:'co_chip',   first:'Rhys',     last:'O\u2019Hara', role:'Sr. RE Analyst',     email:'rohara@chipotle.com',        phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'linkedin',  linkedin:true,  notes:'' },
  { id:'ct_trent',   company_id:'co_honey',  first:'Trent',    last:'Ismail',  role:'Head of Real Estate',    email:'tismail@honeygrow.com',      phone:'(215) 555-0181', verif:'verified',   last_verified_days:34, last_contacted_days:112, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_kia_hg',  company_id:'co_honey',  first:'Kianna',   last:'Park',    role:'Real Estate Manager',    email:'kpark@honeygrow.com',        phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'costar_import',linkedin:false, notes:'' },
  { id:'ct_jim_jm',  company_id:'co_jersey', first:'James',    last:'Corso',   role:'VP Franchise Development',email:'jcorso@jerseymikes.com',    phone:'(732) 555-0145', verif:'verified',   last_verified_days:22, last_contacted_days:null, last_reply_days:null, source:'apollo',       linkedin:true,  notes:'' },
  { id:'ct_melia',   company_id:'co_jersey', first:'Amelia',   last:'Donnelly',role:'Franchise RE Coordinator',email:'adonnelly@jerseymikes.com', phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'apollo',    linkedin:false, notes:'' },
  { id:'ct_dig_1',   company_id:'co_cava_b', first:'Peter',    last:'Alvarez', role:'Real Estate (former)',   email:'peter@diginn.com',           phone:null,             verif:'stale',      last_verified_days:180,last_contacted_days:210,last_reply_days:null,source:'apollo',    linkedin:true,  notes:'LinkedIn shows he left in Feb. Needs re-enrich.' },
  { id:'ct_dig_2',   company_id:'co_cava_b', first:'Rosa',     last:'Greenberg',role:'VP Operations',         email:'rosa@diginn.com',            phone:'(212) 555-0190', verif:'unverified', last_verified_days:120,last_contacted_days:null,last_reply_days:null,source:'manual',    linkedin:false, notes:'Not explicitly RE but reported to be handling expansion post-reorg.' },
  { id:'ct_pnr_1',   company_id:'co_panera', first:'Julia',    last:'Ostrowski',role:'Director, Real Estate', email:'jostrowski@panerabread.com', phone:'(314) 555-0120', verif:'verified',   last_verified_days:48, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_pnr_2',   company_id:'co_panera', first:'Frank',    last:'Demarco', role:'Market Leader, Northeast',email:'fdemarco@panerabread.com',  phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'costar_import',linkedin:true, notes:'' },
  { id:'ct_cane_1',  company_id:'co_cane',   first:'Elliot',   last:'Washington',role:'Dir. of Site Selection',email:'ewashington@raisingcanes.com', phone:'(225) 555-0117', verif:'verified', last_verified_days:14, last_contacted_days:30, last_reply_days:32, source:'apollo',        linkedin:true,  notes:'' },
  { id:'ct_wing_1',  company_id:'co_wingst', first:'Marisa',   last:'Delgado', role:'Head of Real Estate',    email:'mdelgado@wingstop.com',      phone:'(972) 555-0188', verif:'verified',   last_verified_days:28, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_wing_2',  company_id:'co_wingst', first:'Dan',      last:'Harker',  role:'Real Estate Analyst',    email:'dharker@wingstop.com',       phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'linkedin',  linkedin:true,  notes:'' },
  { id:'ct_cfa_1',   company_id:'co_chick',  first:'Travis',   last:'Bickley', role:'Real Estate Manager',    email:'tbickley@chick-fil-a.com',   phone:null,             verif:'bounced',    last_verified_days:60, last_contacted_days:60, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'Last send bounced. LinkedIn active; try new alias?' },
  { id:'ct_cfa_2',   company_id:'co_chick',  first:'Holland',  last:'Reed',    role:'Director, Corp. Development',email:'hreed@chick-fil-a.com',  phone:'(678) 555-0155', verif:'verified',   last_verified_days:60, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_fw_1',    company_id:'co_first',  first:'Logan',    last:'Park',    role:'VP Real Estate',         email:'lpark@firstwatch.com',       phone:'(941) 555-0122', verif:'verified',   last_verified_days:9,  last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_fw_2',    company_id:'co_first',  first:'Naomi',    last:'Cruz',    role:'RE Manager, Northeast',  email:'ncruz@firstwatch.com',       phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'costar_import',linkedin:false, notes:'' },
  { id:'ct_rohan',   company_id:'co_joe',    first:'Rohan',    last:'Patel',   role:'Real Estate',            email:'rohan@joejuice.com',         phone:'(646) 555-0139', verif:'verified',   last_verified_days:7,  last_contacted_days:3, last_reply_days:null, source:'apollo',        linkedin:true,  notes:'' },
  { id:'ct_claud',   company_id:'co_blank',  first:'Claudia',  last:'Bernal',  role:'Expansion Lead',         email:'claudia@blankstreet.com',    phone:'(917) 555-0142', verif:'verified',   last_verified_days:20, last_contacted_days:3, last_reply_days:4, source:'apollo',        linkedin:true,  notes:'' },
  { id:'ct_bs_2',    company_id:'co_blank',  first:'Oren',     last:'Silva',   role:'Real Estate Associate',  email:'oren@blankstreet.com',       phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'manual',    linkedin:false, notes:'' },
  { id:'ct_bb_1',    company_id:'co_bluebot',first:'Mia',      last:'Nakamura',role:'Director of Real Estate',email:'mnakamura@bluebottlecoffee.com',phone:'(415) 555-0166', verif:'verified', last_verified_days:38, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_st_1',    company_id:'co_stumpt', first:'Gavin',    last:'Connor',  role:'Real Estate (contractor)',email:'gavin@stumptowncoffee.com', phone:null,             verif:'stale',      last_verified_days:160,last_contacted_days:190,last_reply_days:null,source:'costar_import',linkedin:true, notes:'' },
  { id:'ct_toma',    company_id:'co_jeni',   first:'Tom\u00e1s',last:'Alvarez',role:'Real Estate',            email:'t.alvarez@jenis.com',        phone:'(614) 555-0199', verif:'verified',   last_verified_days:21, last_contacted_days:4, last_reply_days:null, source:'apollo',        linkedin:true,  notes:'' },
  { id:'ct_jn_2',    company_id:'co_jeni',   first:'Sadie',    last:'Chen',    role:'Development Analyst',    email:'schen@jenis.com',            phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'linkedin',  linkedin:true,  notes:'' },
  { id:'ct_lv_1',    company_id:'co_levain', first:'Rachel',   last:'Woodley', role:'Head of Real Estate',    email:'rwoodley@levainbakery.com',  phone:'(212) 555-0123', verif:'verified',   last_verified_days:40, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_vl_1',    company_id:'co_vansl',  first:'Henry',    last:'Kaplan',  role:'Director of Expansion',  email:'hkaplan@vanleeuwenicecream.com',phone:'(917) 555-0170', verif:'verified',last_verified_days:70, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_ss_1',    company_id:'co_saltgr', first:'Lucia',    last:'Beltran', role:'Director of Real Estate',email:'lucia@saltandstraw.com',     phone:'(503) 555-0189', verif:'verified',   last_verified_days:55, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_jess',    company_id:'co_warby',  first:'Jessica',  last:'Wen',     role:'Director, RE Strategy',  email:'jwen@warbyparker.com',       phone:'(646) 555-0111', verif:'verified',   last_verified_days:15, last_contacted_days:1, last_reply_days:1, source:'apollo',        linkedin:true,  notes:'Very responsive. Prefers email to calls.' },
  { id:'ct_wp_2',    company_id:'co_warby',  first:'Elena',    last:'Volkov',  role:'Real Estate Manager',    email:'evolkov@warbyparker.com',    phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'linkedin',  linkedin:true,  notes:'' },
  { id:'ct_alo_1',   company_id:'co_aloyoga',first:'Priya',    last:'Sethi',   role:'VP Real Estate',         email:'psethi@aloyoga.com',         phone:'(310) 555-0141', verif:'verified',   last_verified_days:46, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_lu_1',    company_id:'co_lulu',   first:'Drew',     last:'Macdonald',role:'Dir., Store Development',email:'dmacdonald@lululemon.com',  phone:'(604) 555-0133', verif:'verified',   last_verified_days:33, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_lu_2',    company_id:'co_lulu',   first:'Taryn',    last:'Hollister',role:'RE Manager, Northeast', email:'thollister@lululemon.com',   phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'costar_import',linkedin:false, notes:'' },
  { id:'ct_sph_1',   company_id:'co_sephora',first:'Monica',   last:'Ferrer',  role:'VP Store Development',   email:'mferrer@sephora.com',        phone:'(415) 555-0177', verif:'verified',   last_verified_days:19, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_gl_1',    company_id:'co_glossier',first:'Ava',     last:'Chen',    role:'Head of Retail Expansion',email:'ava@glossier.com',          phone:'(646) 555-0129', verif:'verified',   last_verified_days:62, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_by_1',    company_id:'co_bark',   first:'Leo',      last:'Maren',   role:'Director of Real Estate',email:'lmaren@barrys.com',          phone:'(212) 555-0150', verif:'verified',   last_verified_days:52, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_sc_1',    company_id:'co_solid',  first:'Zoe',      last:'Armstrong',role:'Sr. RE Manager',        email:'zarmstrong@solidcore.co',    phone:'(202) 555-0115', verif:'verified',   last_verified_days:11, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_ot_1',    company_id:'co_orange', first:'Patrick',  last:'O\u2019Neill',role:'Franchisee, Westchester',email:'patrick@otfwestchester.com',phone:'(914) 555-0101', verif:'stale', last_verified_days:130,last_contacted_days:160,last_reply_days:null,source:'manual',    linkedin:false, notes:'' },
  { id:'ct_er_1',    company_id:'co_erewhon',first:'Ines',     last:'Varga',   role:'Director of Real Estate',email:'ines@erewhonmarket.com',     phone:'(310) 555-0136', verif:'verified',   last_verified_days:42, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_om_1',    company_id:'co_onemed', first:'Marcus',   last:'Thales',  role:'Head of Real Estate',    email:'mthales@onemedical.com',     phone:'(415) 555-0192', verif:'verified',   last_verified_days:25, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_om_2',    company_id:'co_onemed', first:'Nina',     last:'Bachman', role:'Real Estate Manager',    email:'nbachman@onemedical.com',    phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'linkedin',  linkedin:true,  notes:'' },
  { id:'ct_we_1',    company_id:'co_westel', first:'Jorge',    last:'Sabatini',role:'Director of Real Estate',email:'jsabatini@westelm.com',      phone:'(212) 555-0191', verif:'verified',   last_verified_days:95, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
  { id:'ct_bb_2',    company_id:'co_bluebot',first:'Ranjit',   last:'Singh',   role:'Real Estate Manager',    email:'rsingh@bluebottlecoffee.com',phone:null,             verif:'unverified', last_verified_days:null,last_contacted_days:null,last_reply_days:null,source:'costar_import',linkedin:false, notes:'' },
  { id:'ct_jn_3',    company_id:'co_jeni',   first:'Mark',     last:'Otieno',  role:'VP Development',         email:'motieno@jenis.com',          phone:'(614) 555-0166', verif:'verified',   last_verified_days:21, last_contacted_days:null, last_reply_days:null, source:'apollo',    linkedin:true,  notes:'' },
];

export const interactions: Interaction[] = [
  { id:'in_1',  contact_id:'ct_britt',  type:'meeting', when_days:9,  who:'Adam Barlow', title:'Intro call',
    summary:'30 min intro over Zoom. Walked through Larchmont thesis; she asked about co-tenancy and drive-up patio access.' },
  { id:'in_2',  contact_id:'ct_britt',  type:'note',    when_days:8,  who:'Adam Barlow',
    summary:'Brittany mentioned her committee approves 3 sites / quarter. We\u2019re in line for the May cycle if we get the LOD in this week.' },
  { id:'in_3',  contact_id:'ct_britt',  type:'enrich',  when_days:6,  who:'System',
    summary:'Apollo re-enrichment confirmed email + role unchanged. Added direct phone.' },
  { id:'in_4',  contact_id:'ct_marcus', type:'meeting', when_days:21, who:'Adam Barlow', title:'Market overview lunch',
    summary:'Lunch at Marea. Marcus shared 2026 target map; Larchmont + Rye Brook both on list.' },
  { id:'in_5',  contact_id:'ct_diane',  type:'note',    when_days:14, who:'Adam Barlow',
    summary:'Diane routed Larchmont file to their SE RE lead, asked us to wait 10 days.' },
  { id:'in_6',  contact_id:'ct_ben',    type:'meeting', when_days:30, who:'Adam Barlow', title:'Chipotlane walkthrough',
    summary:'Walked the 1842 Boston Post Rd lot together. Ben said the fuel-canopy teardown makes CL feasible.' },
  { id:'in_7',  contact_id:'ct_rohan',  type:'note',    when_days:12, who:'Adam Barlow',
    summary:'Rohan prefers 800-1200 SF inline over endcaps in suburban markets.' },
  { id:'in_8',  contact_id:'ct_jess',   type:'meeting', when_days:1,  who:'Adam Barlow', title:'Scottsdale Fashion Sq recap',
    summary:'Jessica moved forward on Scottsdale. Asked us to keep her in loop on Westchester if 1,800 SF opens up.' },
  { id:'in_9',  contact_id:'ct_cane_1', type:'meeting', when_days:30, who:'Adam Barlow', title:'Tour \u2014 White Plains',
    summary:'Site tour of three White Plains parcels; Elliot most interested in the Tarrytown Rd option.' },
  { id:'in_10', contact_id:'ct_dig_1',  type:'note',    when_days:30, who:'Adam Barlow',
    summary:'Peter left Dig Inn per LinkedIn. Need re-enrich or new contact.' },
];

// Lookup helpers
export const companiesById = Object.fromEntries(companies.map(c => [c.id, c]));
export const contactsById = Object.fromEntries(contacts.map(c => [c.id, c]));

export function contactsForCompany(companyId: string): Contact[] {
  return contacts.filter(c => c.company_id === companyId);
}

export function contactFullName(c: Contact): string {
  return `${c.first} ${c.last}`;
}

export function contactInitials(c: Contact): string {
  return `${(c.first || '?')[0]}${(c.last || '?')[0]}`.toUpperCase();
}

export function sectorBg(sector: string): string {
  return sectorColor[sector] || '#3A5BA0';
}

export const verifLabel: Record<VerificationStatus, { label: string; bg: string; fg: string; dot: string }> = {
  verified:   { label: 'Verified',   bg: '#E3F1E5', fg: '#2F7A3B', dot: '#2F7A3B' },
  unverified: { label: 'Unverified', bg: '#F2F5F9', fg: '#596779', dot: '#A7ADB7' },
  stale:      { label: 'Stale',      bg: '#FBEFC8', fg: '#8A6417', dot: '#E5B85C' },
  bounced:    { label: 'Bounced',    bg: '#FCE3DA', fg: '#C25E1F', dot: '#C25E1F' },
};

export function sourceLabel(s: string): string {
  return ({ apollo: 'Apollo', linkedin: 'LinkedIn', costar_import: 'CoStar import', manual: 'Manual' } as Record<string, string>)[s] || s;
}

export function formatRelDays(days: number | null | undefined): string {
  if (days === null || days === undefined) return '\u2014';
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.round(days / 7)}w ago`;
  if (days < 365) return `${Math.round(days / 30)}mo ago`;
  return `${Math.round(days / 365)}y ago`;
}

export function formatSF(min: number, max: number): string {
  if (!min && !max) return '\u2014';
  if (min && max) return `${(min / 1000).toFixed(1).replace(/\.0$/, '')}\u2013${(max / 1000).toFixed(1).replace(/\.0$/, '')}K sf`;
  return `${((min || max) / 1000).toFixed(1).replace(/\.0$/, '')}K sf`;
}
