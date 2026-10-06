import sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from collect import normalize
class DVFTest(unittest.TestCase):
 def base(self):return dict(id_mutation='1',nature_mutation='Vente',valeur_fonciere='100000',id_parcelle='53130000AM01',adresse_numero='1',adresse_suffixe='',adresse_code_voie='001',type_local='Appartement',surface_reelle_bati='40',nombre_pieces_principales='2',lot1_numero='1',lot2_numero='',lot3_numero='',lot4_numero='',lot5_numero='',numero_disposition='1',longitude='-.77',latitude='48.07',date_mutation='2024-01-01',code_commune='53130',nom_commune='Laval',adresse_nom_voie='RUE TEST')
 def test_repeat_not_sum(self):
  r=self.base();out,a=normalize([r,r.copy()]);self.assertEqual(len(out),1);self.assertEqual(out[0]['price'],100000);self.assertEqual(out[0]['ppm'],2500)
 def test_multibien_excluded(self):
  r=self.base();s={**r,'lot1_numero':'2'};out,a=normalize([r,s]);self.assertEqual(out,[]);self.assertEqual(a['excluded']['multi-biens ou sans logement'],1)
 def test_ambiguous_price_excluded(self):
  r=self.base();out,a=normalize([r,{**r,'valeur_fonciere':'200000'}]);self.assertEqual(out,[])
 def test_missing_area(self):
  r=self.base();r['surface_reelle_bati']='';out,a=normalize([r]);self.assertEqual(out,[])
 def test_dependency_price_kept_once(self):
  r=self.base();out,a=normalize([r,{**r,'type_local':'Dépendance','surface_reelle_bati':'0'}]);self.assertEqual(out[0]['price'],100000);self.assertTrue(out[0]['dependencies'])
if __name__=='__main__':unittest.main()
