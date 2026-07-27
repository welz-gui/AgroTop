import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../data/animal_repository.dart';
import '../domain/animal_model.dart';
import 'animal_detail_page.dart';

class AnimalListPage extends StatefulWidget {
  const AnimalListPage({super.key});

  @override
  State<AnimalListPage> createState() => _AnimalListPageState();
}

class _AnimalListPageState extends State<AnimalListPage> {
  final AnimalRepository _repository = AnimalRepository();
  List<AnimalModel> _animals = [];
  List<AnimalModel> _filteredAnimals = [];
  bool _isLoading = true;
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadAnimals();
  }

  Future<void> _loadAnimals() async {
    final list = await _repository.fetchAnimals();
    setState(() {
      _animals = list;
      _filteredAnimals = list;
      _isLoading = false;
    });
  }

  void _onSearchChanged(String query) {
    setState(() {
      if (query.isEmpty) {
        _filteredAnimals = _animals;
      } else {
        _filteredAnimals = _animals.where((a) {
          return a.id.toLowerCase().contains(query.toLowerCase()) ||
              a.breed.toLowerCase().contains(query.toLowerCase()) ||
              (a.loteId ?? '').toLowerCase().contains(query.toLowerCase());
        }).toList();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Rebanho Ativo'),
      ),
      body: Column(
        children: [
          // Campo de busca por brinco / raça / piquete
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: 'Buscar por brinco, raça ou piquete...',
                prefixIcon: const Icon(Icons.search, color: AppColors.primary),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          _onSearchChanged('');
                        },
                      )
                    : null,
              ),
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _filteredAnimals.isEmpty
                    ? const Center(
                        child: Text(
                          'Nenhum animal encontrado.',
                          style: TextStyle(fontSize: 16, color: AppColors.textSecondary),
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        itemCount: _filteredAnimals.length,
                        itemBuilder: (context, index) {
                          final animal = _filteredAnimals[index];
                          return Card(
                            margin: const EdgeInsets.only(bottom: 12),
                            child: ListTile(
                              contentPadding: const EdgeInsets.all(12),
                              leading: CircleAvatar(
                                radius: 24,
                                backgroundColor: AppColors.primary.withOpacity(0.12),
                                child: Text(
                                  animal.sex,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.primary,
                                  ),
                                ),
                              ),
                              title: Text(
                                animal.id,
                                style: const TextStyle(
                                  fontSize: 17,
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.textPrimary,
                                ),
                              ),
                              subtitle: Text(
                                '${animal.breed} • ${animal.loteId ?? 'Sem Piquete'}',
                                style: const TextStyle(
                                  fontSize: 14,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                              trailing: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(
                                    '${animal.currentWeight ?? 0} kg',
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                      color: AppColors.primary,
                                    ),
                                  ),
                                  Text(
                                    '+${animal.gmd ?? 0} kg/dia',
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: AppColors.alertSuccess,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                              onTap: () {
                                Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => AnimalDetailPage(animal: animal),
                                  ),
                                );
                              },
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
