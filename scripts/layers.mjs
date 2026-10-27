// Prints the map style layers for the "protomaps" vector source: Protomaps "light" or
// "dark" flavor (argument, default light) with Hebrew labels (Latin script where there
// is no Hebrew name).
import { layers, namedFlavor } from '@protomaps/basemaps';

const flavor = process.argv[2] || 'light';
const result = layers('protomaps', namedFlavor(flavor), { lang: 'he' });
process.stdout.write(JSON.stringify(result));
