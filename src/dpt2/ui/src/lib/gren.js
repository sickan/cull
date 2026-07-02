// Gren-markör (Herr/Dam/Mix/ej satt) — egen dämpad palett, medvetet fristående
// från Skagen-temats Hav/Sol/Rosé som kodar innehållstyp. Rena hex (ej tokens)
// så färgerna är identiska i ljust och mörkt tema.
export const GREN_FARG = { herr: '#3E7C87', dam: '#8E5A86', mixed: '#6E8757' }
export const grenFarg = (g) => GREN_FARG[g] || '#8A8172' // fallback = neutral (ej satt)
export const grenEtikett = (g) => ({ herr: 'Herr', dam: 'Dam', mixed: 'Mix' }[g] || '') // ej satt = ingen label
