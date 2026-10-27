// Prints the map style layers for the "protomaps" vector source: Protomaps "light"
// flavor with Hebrew labels (Latin script where there is no Hebrew name).
import { layers, namedFlavor } from '@protomaps/basemaps';

const result = layers('protomaps', namedFlavor('light'), { lang: 'he' });
process.stdout.write(JSON.stringify(result));
