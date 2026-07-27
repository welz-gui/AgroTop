import '../../../core/network/supabase_client.dart';
import '../domain/animal_model.dart';

class AnimalRepository {
  /// Busca todos os animais ativos do Supabase
  Future<List<AnimalModel>> fetchAnimals({String status = 'ativo'}) async {
    try {
      final response = await SupabaseConfig.client
          .from('animals')
          .select()
          .eq('status', status)
          .order('animal_id', ascending: true);

      return (response as List).map((json) => AnimalModel.fromJson(json)).toList();
    } catch (e) {
      // Fallback para lista demonstrativa caso esteja offline ou banco não configurado
      return [
        AnimalModel(
          id: 'BR-1001',
          breed: 'Nelore',
          sex: 'M',
          entryDate: '2025-10-15',
          loteId: 'PIQUETE-01',
          status: 'ativo',
          currentWeight: 420.5,
          gmd: 0.950,
        ),
        AnimalModel(
          id: 'BR-1002',
          breed: 'Angus',
          sex: 'M',
          entryDate: '2025-11-01',
          loteId: 'PIQUETE-02',
          status: 'ativo',
          currentWeight: 445.0,
          gmd: 1.120,
        ),
        AnimalModel(
          id: 'BR-1003',
          breed: 'Cruzamento Industrial',
          sex: 'F',
          entryDate: '2025-12-10',
          loteId: 'PIQUETE-01',
          status: 'ativo',
          currentWeight: 380.0,
          gmd: 0.820,
        ),
      ];
    }
  }

  /// Cadastra um novo animal no Supabase
  Future<void> addAnimal(AnimalModel animal) async {
    await SupabaseConfig.client.from('animals').insert(animal.toJson());
  }

  /// Busca a ficha individual de um animal pelo código/brinco
  Future<AnimalModel?> getAnimal(String animalId) async {
    final response = await SupabaseConfig.client
        .from('animals')
        .select()
        .eq('animal_id', animalId)
        .maybeSingle();

    if (response == null) return null;
    return AnimalModel.fromJson(response);
  }
}
