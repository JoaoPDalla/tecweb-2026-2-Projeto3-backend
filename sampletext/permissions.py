from rest_framework.permissions import BasePermission


class IsDono(BasePermission):
    """Só deixa mexer em objetos cujo campo `usuario` é o usuário logado."""

    message = "Você não tem permissão para acessar este item."

    def has_object_permission(self, request, view, obj):
        return getattr(obj, "usuario_id", None) == request.user.pk


class DonoQuerysetMixin:
    """Para ViewSets de modelos com FK `usuario` (ex.: Livro, Conteudo).

    - listagens e buscas só enxergam os itens do usuário logado;
    - itens criados já ficam associados ao usuário logado.
    Use junto com `permission_classes = [IsAuthenticated, IsDono]`.
    """

    def get_queryset(self):
        return super().get_queryset().filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)
