
import { useEffect, useMemo, useRef, useState } from 'react'

const API_URL = '/api/utilisateurs/'
const BUSINESS_TIME_ZONE = 'Africa/Ouagadougou'

function formatBusinessDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: BUSINESS_TIME_ZONE,
  }).format(date)
}

function formatBusinessDate(value) {
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? `${value}T12:00:00Z`
    : value
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeZone: BUSINESS_TIME_ZONE,
  }).format(date)
}

const navigation = [
  { id: 'dashboard', icon: '▦', label: 'Tableau de bord' },
  { id: 'pieces', icon: '▤', label: 'Pièces détachées' },
  { id: 'stock', icon: '⇄', label: 'Mouvements de stock' },
  { id: 'fournisseurs', icon: '♧', label: 'Fournisseurs' },
  { id: 'ventes', icon: '▣', label: 'Ventes' },
  { id: 'clients', icon: '♙', label: 'Clients' },
  { id: 'factures', icon: '▧', label: 'Factures' },
  { id: 'caisse', icon: '₣', label: 'Caisse' },
  { id: 'rapports', icon: '▥', label: 'Rapports' },
  { id: 'utilisateurs', icon: '♙', label: 'Utilisateurs et rôles' },
  { id: 'parametres-magasin', icon: '⚙', label: 'Paramètres du magasin' },
]

const roleLabels = {
  Administrateur: 'Administrateur',
  'Responsable magasin': 'Responsable magasin',
  'Gestionnaire de stock': 'Gestionnaire de stock',
  Vendeur: 'Vendeur',
  Caissier: 'Caissier',
}

const rolePermissionModules = [
  ['utilisateurs', 'Utilisateurs'],
  ['stock', 'Stock'],
  ['clients', 'Clients'],
  ['fournisseurs', 'Fournisseurs'],
  ['ventes', 'Ventes'],
  ['factures', 'Factures'],
  ['rapports', 'Rapports'],
  ['caisse', 'Caisse'],
]

const permissionLabels = {
  gestion: 'Gestion',
  lecture: 'Lecture',
  aucun: 'Aucun',
  absent: 'Non disponible',
}

const emptyPieceForm = {
  reference: '',
  designation: '',
  categorie: '',
  marque: '',
  modeles_compatibles: '',
  unite: 'unité',
  prix_achat: '',
  prix_vente: '',
  seuil_minimal: '0',
  emplacement: '',
}

const emptyMovementForm = {
  piece: '',
  type_mouvement: 'ENTREE',
  quantite: '',
  prix_unitaire: '0',
  motif: '',
  reference_document: '',
  observation: '',
}

const emptyUserForm = {
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  mot_de_passe: '',
  roles: [],
}

const emptyClientForm = {
  nom: '',
  telephone: '',
  adresse: '',
}

const emptySupplierForm = {
  nom: '',
  telephone: '',
  email: '',
  adresse: '',
}

async function getCsrfToken() {
  const response = await fetch('/api/auth/csrf/', { credentials: 'include' })

  if (!response.ok) {
    throw new Error('Impossible de préparer la requête sécurisée.')
  }

  const data = await response.json()
  const cookie = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrftoken='))
    ?.split('=')[1]

  return cookie || data.csrfToken
}

function App() {
  const [page, setPage] = useState('dashboard')
  const [users, setUsers] = useState([])
  const [clients, setClients] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [supplierPurchases, setSupplierPurchases] = useState([])
  const [purchaseForm, setPurchaseForm] = useState({
    fournisseur: '',
    lignes: [{ piece: '', quantite: '1', prix_unitaire: '' }],
  })
  const [sales, setSales] = useState([])
  const [saleReturns, setSaleReturns] = useState([])
  const [editingSaleId, setEditingSaleId] = useState(null)
  const [selectedReturnSale, setSelectedReturnSale] = useState(null)
  const [returnReason, setReturnReason] = useState('')
  const [returnQuantities, setReturnQuantities] = useState({})
  const [selectedCancellationSale, setSelectedCancellationSale] = useState(null)
  const [cancellationReason, setCancellationReason] = useState('')
  const [dashboardData, setDashboardData] = useState(null)
  const [reportStartDate, setReportStartDate] = useState('')
  const [reportEndDate, setReportEndDate] = useState('')
  const [exportType, setExportType] = useState('indicateurs')
  const [exportFormat, setExportFormat] = useState('xlsx')
  const [exportPieceId, setExportPieceId] = useState('')
  const [exportUserId, setExportUserId] = useState('')
  const [exportMovementType, setExportMovementType] = useState('')
  const [invoices, setInvoices] = useState([])
  const [cashInvoices, setCashInvoices] = useState([])
  const [encaissements, setEncaissements] = useState([])
  const [remboursements, setRemboursements] = useState([])
  const [cloturesCaisse, setCloturesCaisse] = useState([])
  const [cashPreview, setCashPreview] = useState(null)
  const [paymentForm, setPaymentForm] = useState({
    facture_id: '',
    montant: '',
    mode_paiement: 'ESPECES',
  })
  const [paymentSubmitting, setPaymentSubmitting] = useState(false)
  const paymentRequestRef = useRef(null)
  const [selectedReceipt, setSelectedReceipt] = useState(null)
  const [selectedPaymentForRefund, setSelectedPaymentForRefund] = useState(null)
  const [refundForm, setRefundForm] = useState({
    montant: '',
    motif: '',
    mode_remboursement: 'ESPECES',
  })
  const [refundSubmitting, setRefundSubmitting] = useState(false)
  const refundRequestRef = useRef(null)
  const [selectedRefundForExecution, setSelectedRefundForExecution] = useState(null)
  const [refundExecutionReference, setRefundExecutionReference] = useState('')
  const [closingCash, setClosingCash] = useState(false)
  const [cashCount, setCashCount] = useState({})
  const [selectedCashInvoice, setSelectedCashInvoice] = useState(null)
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(null)
  const [saleClientId, setSaleClientId] = useState('')
  const [saleLines, setSaleLines] = useState([{ piece: '', quantite: '1' }])
  const [supplierForm, setSupplierForm] = useState(emptySupplierForm)
  const [editingSupplierId, setEditingSupplierId] = useState(null)
  const [clientForm, setClientForm] = useState(emptyClientForm)
  const [editingClientId, setEditingClientId] = useState(null)
  const [availableRoles, setAvailableRoles] = useState([])
  const [effectiveRolePermissions, setEffectiveRolePermissions] = useState([])
  const [userForm, setUserForm] = useState(emptyUserForm)
  const [editingUserId, setEditingUserId] = useState(null)
  const [pieces, setPieces] = useState([])
  const [categories, setCategories] = useState([])
  const [movements, setMovements] = useState([])
  const [inventoryLoading, setInventoryLoading] = useState(false)
  const [inventoryError, setInventoryError] = useState('')
  const [pieceForm, setPieceForm] = useState(emptyPieceForm)
  const [editingPieceId, setEditingPieceId] = useState(null)
  const [categoryName, setCategoryName] = useState('')
  const [movementForm, setMovementForm] = useState(emptyMovementForm)
  const movementRequestKey = useRef(null)
  const [inventorySearch, setInventorySearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [lastUpdate, setLastUpdate] = useState(null)
  const [currentUser, setCurrentUser] = useState(null)
  const [profilePasswordOpen, setProfilePasswordOpen] = useState(false)
  const [profilePasswordForm, setProfilePasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  const [profilePasswordError, setProfilePasswordError] = useState('')
  const [profilePasswordSuccess, setProfilePasswordSuccess] = useState('')
  const [profilePasswordSaving, setProfilePasswordSaving] = useState(false)
  const [passwordResetUser, setPasswordResetUser] = useState(null)
  const [adminPasswordForm, setAdminPasswordForm] = useState({
    new_password: '',
    confirm_password: '',
  })
  const [adminPasswordError, setAdminPasswordError] = useState('')
  const [adminPasswordSuccess, setAdminPasswordSuccess] = useState('')
  const [adminPasswordSaving, setAdminPasswordSaving] = useState(false)
  const sessionEpochRef = useRef(0)
  const [storeSettings, setStoreSettings] = useState(null)
  const [storeSettingsLoading, setStoreSettingsLoading] = useState(false)
  const [storeSettingsSaving, setStoreSettingsSaving] = useState(false)
  const [storeSettingsError, setStoreSettingsError] = useState('')
  const [storeSettingsSuccess, setStoreSettingsSuccess] = useState('')
  const [storeLogoFile, setStoreLogoFile] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const [username, setUsername] = useState('')
const [password, setPassword] = useState('')

function clearUserData() {
  sessionEpochRef.current += 1
  setUsers([])
  setClients([])
  setSuppliers([])
  setSupplierPurchases([])
  setSales([])
  setSaleReturns([])
  setDashboardData(null)
  setInvoices([])
  setCashInvoices([])
  setEncaissements([])
  setRemboursements([])
  setCloturesCaisse([])
  setCashPreview(null)
  setSelectedReceipt(null)
  setSelectedPaymentForRefund(null)
  setSelectedRefundForExecution(null)
  setSelectedCashInvoice(null)
  setSelectedInvoiceId(null)
  setPieces([])
  setCategories([])
  setMovements([])
  setStoreSettings(null)
  setStoreSettingsError('')
  setStoreSettingsSuccess('')
  setStoreLogoFile(null)
  setSelectedReturnSale(null)
  setSelectedCancellationSale(null)
  setProfilePasswordOpen(false)
  setProfilePasswordForm({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  setProfilePasswordError('')
  setProfilePasswordSuccess('')
  setPasswordResetUser(null)
  setAdminPasswordForm({ new_password: '', confirm_password: '' })
  setAdminPasswordError('')
  setAdminPasswordSuccess('')
  setAvailableRoles([])
  setEffectiveRolePermissions([])
  setInventoryError('')
  setInventoryLoading(false)
  setError('')
  setLastUpdate(null)
  setPage('dashboard')
}

useEffect(() => {
    let active = true

    fetch('/api/auth/session/', { credentials: 'include' })
      .then((response) => (response.ok ? response.json() : null))
      .then((user) => {
        if (active && user) {
          clearUserData()
          setCurrentUser(user)
          loadCatalog()
          loadDashboard()
        }
      })
      .catch(() => {})
      .finally(() => {
        if (active) setAuthLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

async function handleLogin(event) {
  event.preventDefault()
  setLoginError('')
  setLoginLoading(true)

  try {
    const csrfToken = await getCsrfToken()
    const response = await fetch('/api/auth/connexion/', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify({ username, password }),
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || 'Échec de la connexion.')
    }

    clearUserData()
    setCurrentUser(data)
    setPassword('')
    setPage('dashboard')
    loadCatalog()
    loadDashboard()
  } catch (err) {
    setLoginError(
      err.message === 'Failed to fetch'
        ? 'Serveur inaccessible. Vérifie que Django fonctionne.'
        : err.message,
    )
  } finally {
    setLoginLoading(false)
  }
}

async function changeOwnPassword(event) {
  event.preventDefault()
  setProfilePasswordError('')
  setProfilePasswordSuccess('')
  if (profilePasswordForm.new_password !== profilePasswordForm.confirm_password) {
    setProfilePasswordError('La confirmation du nouveau mot de passe ne correspond pas.')
    return
  }

  setProfilePasswordSaving(true)
  try {
    const csrfToken = await getCsrfToken()
    const response = await fetch('/api/auth/mot-de-passe/', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify({
        current_password: profilePasswordForm.current_password,
        new_password: profilePasswordForm.new_password,
      }),
    })
    const data = await response.json()
    if (!response.ok) {
      const message = data.detail
        || Object.values(data).flat().join(' ')
        || 'Le changement de mot de passe a échoué.'
      throw new Error(message)
    }

    setProfilePasswordForm({
      current_password: '',
      new_password: '',
      confirm_password: '',
    })
    setProfilePasswordSuccess(data.detail)
  } catch (err) {
    setProfilePasswordError(err.message)
  } finally {
    setProfilePasswordSaving(false)
  }
}

async function resetUserPassword(event) {
  event.preventDefault()
  setAdminPasswordError('')
  setAdminPasswordSuccess('')
  if (adminPasswordForm.new_password !== adminPasswordForm.confirm_password) {
    setAdminPasswordError('La confirmation du nouveau mot de passe ne correspond pas.')
    return
  }

  setAdminPasswordSaving(true)
  try {
    const csrfToken = await getCsrfToken()
    const response = await fetch(
      `/api/utilisateurs/${passwordResetUser.id}/reinitialiser-mot-de-passe/`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ new_password: adminPasswordForm.new_password }),
      },
    )
    const data = await response.json()
    if (!response.ok) {
      const message = data.detail
        || Object.values(data).flat().join(' ')
        || 'La réinitialisation du mot de passe a échoué.'
      throw new Error(message)
    }

    setAdminPasswordForm({ new_password: '', confirm_password: '' })
    setAdminPasswordSuccess(data.detail)
  } catch (err) {
    setAdminPasswordError(err.message)
  } finally {
    setAdminPasswordSaving(false)
  }
}

  async function handleLogout() {
    setLoginError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch('/api/auth/deconnexion/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRFToken': csrfToken },
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Échec de la déconnexion.')
      }

      clearUserData()
      setCurrentUser(null)
    } catch (err) {
      setLoginError(
        err.message === 'Failed to fetch'
          ? 'Serveur inaccessible. Vérifie que Django fonctionne.'
          : err.message,
      )
    }
  }
  async function loadStoreSettings() {
  setStoreSettingsLoading(true)
  setStoreSettingsError('')
  setStoreSettingsSuccess('')

  try {
    const response = await fetch('/api/store-settings/', {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })

    if (!response.ok) {
      throw new Error('Impossible de charger les paramètres du magasin.')
    }

    const data = await response.json()
    setStoreSettings(data)
    setStoreLogoFile(null)
    return data
  } catch (err) {
    setStoreSettingsError(err.message)
    return null
  } finally {
    setStoreSettingsLoading(false)
  }
}
  
  
async function saveStoreSettings() {
  if (!canEditStoreSettings || !storeSettings) return

  setStoreSettingsSaving(true)
  setStoreSettingsError('')
  setStoreSettingsSuccess('')

  try {
    const csrfToken = await getCsrfToken()
    const formData = new FormData()

    formData.append('nom_magasin', storeSettings.nom_magasin || '')
    formData.append('adresse', storeSettings.adresse || '')
    formData.append('telephone', storeSettings.telephone || '')
    formData.append('email', storeSettings.email || '')
    formData.append('pied_de_page', storeSettings.pied_de_page || '')

    if (storeLogoFile) {
      formData.append('logo', storeLogoFile)
    }

    const response = await fetch('/api/store-settings/', {
      method: 'PATCH',
      credentials: 'include',
      headers: {
        'X-CSRFToken': csrfToken,
      },
      body: formData,
    })

    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      throw new Error(
        data.detail || JSON.stringify(data) || 'Échec de l’enregistrement.'
      )
    }

    setStoreSettings(data)
    setStoreLogoFile(null)
    setStoreSettingsSuccess('Les paramètres du magasin ont été enregistrés.')
  } catch (err) {
    setStoreSettingsError(err.message)
  } finally {
    setStoreSettingsSaving(false)
  }
}

  async function loadUsers() {
    setLoading(true)
    setError('')

    try {
      const [response, rolesResponse, permissionsResponse] = await Promise.all([
        fetch(API_URL, { credentials: 'include', headers: { Accept: 'application/json' } }),
        fetch('/api/roles/', { credentials: 'include', headers: { Accept: 'application/json' } }),
        fetch('/api/roles/effectifs/', { credentials: 'include', headers: { Accept: 'application/json' } }),
      ])

      if (!response.ok || !rolesResponse.ok || !permissionsResponse.ok) {
        throw new Error(
          response.status === 403
            ? 'Accès refusé. Connecte-toi avec un compte autorisé.'
            : `Erreur du serveur (${response.status}).`,
        )
      }

      const [data, rolesData, permissionsData] = await Promise.all([
        response.json(),
        rolesResponse.json(),
        permissionsResponse.json(),
      ])
      setUsers(Array.isArray(data) ? data : data.results || [])
      setAvailableRoles(Array.isArray(rolesData) ? rolesData : rolesData.results || [])
      setEffectiveRolePermissions(permissionsData)
      setLastUpdate(new Date())
    } catch (err) {
      setError(
        err.message === 'Failed to fetch'
          ? 'Impossible de joindre Django. Vérifie que le serveur backend fonctionne et que les autorisations CORS sont configurées.'
          : err.message,
      )
    } finally {
      setLoading(false)
    }
  }

  function editUser(user) {
    setEditingUserId(user.id)
    setUserForm({
      username: user.username,
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      email: user.email || '',
      mot_de_passe: '',
      roles: user.roles || [],
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function saveUser(event) {
    event.preventDefault()
    setError('')

    const payload = { ...userForm }
    if (!payload.mot_de_passe) delete payload.mot_de_passe

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(
        editingUserId ? `${API_URL}${editingUserId}/` : API_URL,
        {
          method: editingUserId ? 'PATCH' : 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify(payload),
        },
      )
      const data = await response.json()

      if (!response.ok) throw new Error(JSON.stringify(data))

      setUserForm(emptyUserForm)
      setEditingUserId(null)
      await loadUsers()
    } catch (err) {
      setError(err.message)
    }
  }

  async function toggleUserStatus(user) {
    setError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(`${API_URL}${user.id}/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ is_active: !user.is_active }),
      })
      const data = await response.json()

      if (!response.ok) throw new Error(JSON.stringify(data))
      await loadUsers()
    } catch (err) {
      setError(err.message)
    }
  }

  async function loadCatalog() {
    setInventoryLoading(true)
    setInventoryError('')

    try {
      const [piecesResponse, categoriesResponse] = await Promise.all([
        fetch('/api/pieces/', { credentials: 'include' }),
        fetch('/api/categories/', { credentials: 'include' }),
      ])

      if (!piecesResponse.ok || !categoriesResponse.ok) {
        throw new Error('Impossible de charger le catalogue.')
      }

      const [piecesData, categoriesData] = await Promise.all([
        piecesResponse.json(),
        categoriesResponse.json(),
      ])
      setPieces(Array.isArray(piecesData) ? piecesData : piecesData.results || [])
      setCategories(
        Array.isArray(categoriesData)
          ? categoriesData
          : categoriesData.results || [],
      )
    } catch (err) {
      setInventoryError(
        err.message === 'Failed to fetch'
          ? 'Impossible de joindre le serveur Django.'
          : err.message,
      )
    } finally {
      setInventoryLoading(false)
    }
  }

  async function loadMovements() {
    setInventoryLoading(true)
    setInventoryError('')

    try {
      const [piecesResponse, movementsResponse] = await Promise.all([
        fetch('/api/pieces/', { credentials: 'include' }),
        fetch('/api/mouvements/', { credentials: 'include' }),
      ])

      if (!piecesResponse.ok || !movementsResponse.ok) {
        throw new Error('Impossible de charger les mouvements de stock.')
      }

      const [piecesData, movementsData] = await Promise.all([
        piecesResponse.json(),
        movementsResponse.json(),
      ])
      setPieces(Array.isArray(piecesData) ? piecesData : piecesData.results || [])
      setMovements(
        Array.isArray(movementsData)
          ? movementsData
          : movementsData.results || [],
      )
    } catch (err) {
      setInventoryError(
        err.message === 'Failed to fetch'
          ? 'Impossible de joindre le serveur Django.'
          : err.message,
      )
    } finally {
      setInventoryLoading(false)
    }
  }

  async function loadClients() {
    setInventoryLoading(true)
    setInventoryError('')

    try {
      const response = await fetch('/api/clients/', { credentials: 'include' })
      if (!response.ok) throw new Error('Impossible de charger les clients.')
      const data = await response.json()
      setClients(Array.isArray(data) ? data : data.results || [])
    } catch (err) {
      setInventoryError(
        err.message === 'Failed to fetch'
          ? 'Impossible de joindre le serveur Django.'
          : err.message,
      )
    } finally {
      setInventoryLoading(false)
    }
  }

  async function loadSuppliers() {
    setInventoryLoading(true)
    setInventoryError('')

    try {
      const [suppliersResponse, purchasesResponse, piecesResponse] = await Promise.all([
        fetch('/api/fournisseurs/', { credentials: 'include' }),
        fetch('/api/achats-fournisseurs/', { credentials: 'include' }),
        fetch('/api/pieces/', { credentials: 'include' }),
      ])
      if (!suppliersResponse.ok || !purchasesResponse.ok || !piecesResponse.ok) {
        throw new Error('Impossible de charger les fournisseurs et achats.')
      }
      const [suppliersData, purchasesData, piecesData] = await Promise.all([
        suppliersResponse.json(),
        purchasesResponse.json(),
        piecesResponse.json(),
      ])
      setSuppliers(Array.isArray(suppliersData) ? suppliersData : suppliersData.results || [])
      setSupplierPurchases(Array.isArray(purchasesData) ? purchasesData : purchasesData.results || [])
      setPieces(Array.isArray(piecesData) ? piecesData : piecesData.results || [])
    } catch (err) {
      setInventoryError(
        err.message === 'Failed to fetch'
          ? 'Impossible de joindre le serveur Django.'
          : err.message,
      )
    } finally {
      setInventoryLoading(false)
    }
  }

  async function loadSales() {
    setInventoryLoading(true)
    setInventoryError('')

    try {
      const [salesResponse, piecesResponse, clientsResponse, returnsResponse] = await Promise.all([
        fetch('/api/ventes/', { credentials: 'include' }),
        fetch('/api/pieces/', { credentials: 'include' }),
        fetch('/api/clients/', { credentials: 'include' }),
        fetch('/api/retours-ventes/', { credentials: 'include' }),
      ])
      if (!salesResponse.ok || !piecesResponse.ok || !clientsResponse.ok || !returnsResponse.ok) {
        throw new Error('Impossible de charger les données des ventes.')
      }

      const [salesData, piecesData, clientsData, returnsData] = await Promise.all([
        salesResponse.json(),
        piecesResponse.json(),
        clientsResponse.json(),
        returnsResponse.json(),
      ])
      setSales(Array.isArray(salesData) ? salesData : salesData.results || [])
      setPieces(Array.isArray(piecesData) ? piecesData : piecesData.results || [])
      setClients(Array.isArray(clientsData) ? clientsData : clientsData.results || [])
      setSaleReturns(Array.isArray(returnsData) ? returnsData : returnsData.results || [])
    } catch (err) {
      setInventoryError(
        err.message === 'Failed to fetch'
          ? 'Impossible de joindre le serveur Django.'
          : err.message,
      )
    } finally {
      setInventoryLoading(false)
    }
  }

  async function loadInvoices() {
    setInventoryLoading(true)
    setInventoryError('')

    try {
      const response = await fetch('/api/factures/', { credentials: 'include' })
      if (!response.ok) throw new Error('Impossible de charger les factures.')
      const data = await response.json()
      const items = Array.isArray(data) ? data : data.results || []
      setInvoices(items)
      const settings = await loadStoreSettings()
      if (!settings) {
        setInventoryError('Les factures sont chargées, mais l’identité du magasin est indisponible pour l’impression.')
      }
      if (selectedInvoiceId && !items.some((invoice) => invoice.id === selectedInvoiceId)) {
        setSelectedInvoiceId(null)
      }
    } catch (err) {
      setInventoryError(
        err.message === 'Failed to fetch'
          ? 'Impossible de joindre le serveur Django.'
          : err.message,
      )
    } finally {
      setInventoryLoading(false)
    }
  }

  async function loadCashData() {
    if (!canAccessCash) {
      setInventoryError("Accès réservé à l'Administrateur et au Caissier.")
      return
    }

    const requestEpoch = sessionEpochRef.current
    setInventoryLoading(true)
    setInventoryError('')

    try {
      const responses = await Promise.all([
        fetch('/api/factures-a-encaisser/', { credentials: 'include' }),
        fetch('/api/encaissements/', { credentials: 'include' }),
        fetch('/api/remboursements/', { credentials: 'include' }),
        fetch('/api/clotures-caisse/', { credentials: 'include' }),
        fetch('/api/clotures-caisse/apercu/', { credentials: 'include' }),
      ])

      if (responses.some((response) => !response.ok)) {
        throw new Error(
          'Impossible de charger les données de la caisse. Vérifie tes droits d’accès.'
        )
      }

      if (requestEpoch !== sessionEpochRef.current) return

      const [invoicesData, paymentsData, refundsData, closuresData, previewData] =
        await Promise.all(responses.map((response) => response.json()))
      const items = (data) => Array.isArray(data) ? data : data.results || []

      setCashInvoices(items(invoicesData))
      setEncaissements(items(paymentsData))
      setRemboursements(items(refundsData))
      setCloturesCaisse(items(closuresData))
      setCashPreview(previewData)
    } catch (error) {
      if (requestEpoch === sessionEpochRef.current) {
        setCashInvoices([])
        setEncaissements([])
        setRemboursements([])
        setCloturesCaisse([])
        setCashPreview(null)
        setInventoryError(error.message)
      }
    } finally {
      if (requestEpoch === sessionEpochRef.current) {
        setInventoryLoading(false)
      }
    }
  }

  async function savePayment(event) {
    event.preventDefault()
    setInventoryError('')

    if (!paymentForm.facture_id || !paymentForm.montant) {
      setInventoryError('Sélectionne une facture et saisis un montant.')
      return
    }

    const payload = {
      facture_id: Number(paymentForm.facture_id),
      montant: paymentForm.montant,
      mode_paiement: paymentForm.mode_paiement,
    }
    const payloadKey = JSON.stringify(payload)
    if (paymentRequestRef.current?.payload !== payloadKey) {
      paymentRequestRef.current = {
        payload: payloadKey,
        key: crypto.randomUUID(),
      }
    }

    setPaymentSubmitting(true)
    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch('/api/encaissements/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'Idempotency-Key': paymentRequestRef.current.key,
        },
        body: JSON.stringify(payload),
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.detail || JSON.stringify(data) || 'Erreur lors de l’encaissement.'
        )
      }

      paymentRequestRef.current = null
      setPaymentForm({
        facture_id: '',
        montant: '',
        mode_paiement: 'ESPECES',
      })
      setSelectedCashInvoice(null)
      await loadCashData()
    } catch (error) {
      setInventoryError(error.message)
    } finally {
      setPaymentSubmitting(false)
    }
  }

  async function loadReceipt(paymentId) {
    setInventoryError('')
    try {
      const response = await fetch(`/api/encaissements/${paymentId}/recu/`, {
        credentials: 'include',
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Impossible de charger le reçu.')
      }
      setSelectedReceipt(data)
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function saveRefund(event) {
    event.preventDefault()
    if (!selectedPaymentForRefund) return
    setInventoryError('')
    setRefundSubmitting(true)

    const payload = {
      encaissement_id: selectedPaymentForRefund.id,
      montant: refundForm.montant,
      motif: refundForm.motif,
      mode_remboursement: refundForm.mode_remboursement,
    }
    const payloadKey = JSON.stringify(payload)
    if (refundRequestRef.current?.payload !== payloadKey) {
      refundRequestRef.current = {
        payload: payloadKey,
        key: crypto.randomUUID(),
      }
    }

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch('/api/remboursements/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'Idempotency-Key': refundRequestRef.current.key,
        },
        body: JSON.stringify(payload),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || JSON.stringify(data))
      }
      refundRequestRef.current = null
      setSelectedPaymentForRefund(null)
      setRefundForm({
        montant: '',
        motif: '',
        mode_remboursement: 'ESPECES',
      })
      await loadCashData()
    } catch (err) {
      setInventoryError(err.message)
    } finally {
      setRefundSubmitting(false)
    }
  }

  async function decideRefund(refundId, decision) {
    setInventoryError('')
    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(
        `/api/remboursements/${refundId}/${decision}/`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'X-CSRFToken': csrfToken },
        },
      )
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || JSON.stringify(data))
      }
      await loadCashData()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  function executeRefund(refund) {
    setSelectedRefundForExecution(refund)
    setRefundExecutionReference('')
  }

  async function confirmRefundExecution(event) {
    event.preventDefault()
    if (!selectedRefundForExecution) return
    const executionReference = refundExecutionReference.trim()
    if (!executionReference) {
      setInventoryError('La référence du justificatif est obligatoire.')
      return
    }
    setInventoryError('')
    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(
        `/api/remboursements/${selectedRefundForExecution.id}/executer/`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            reference_execution: executionReference.trim(),
          }),
        },
      )
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || JSON.stringify(data))
      }
      setSelectedRefundForExecution(null)
      setRefundExecutionReference('')
      await loadCashData()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function closeCash() {
    if (!window.confirm('Confirmer la clôture définitive de la caisse du jour ?')) {
      return
    }
    setInventoryError('')
    setClosingCash(true)
    const comptage = Object.fromEntries(
      Object.entries(cashCount).filter(([, amount]) => amount !== ''),
    )

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch('/api/clotures-caisse/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ comptage }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || JSON.stringify(data))
      }
      setCashCount({})
      await loadCashData()
    } catch (err) {
      setInventoryError(err.message)
    } finally {
      setClosingCash(false)
    }
  }

  async function loadDashboard(startDate = '', endDate = '') {
    setInventoryError('')
    const query = new URLSearchParams()
    if (startDate) query.set('date_debut', startDate)
    if (endDate) query.set('date_fin', endDate)
    const suffix = query.size ? `?${query.toString()}` : ''

    try {
      const response = await fetch(`/api/rapports/tableau-de-bord/${suffix}`, {
        credentials: 'include',
      })
      const data = await response.json()
      if (!response.ok) throw new Error(JSON.stringify(data))
      setDashboardData(data)
    } catch (err) {
      setInventoryError(
        err.message === 'Failed to fetch'
          ? 'Impossible de joindre le serveur Django.'
          : err.message,
      )
    }
  }

  function filterDashboard(event) {
    event.preventDefault()
    loadDashboard(reportStartDate, reportEndDate)
  }

  async function downloadReportExport() {
    setInventoryError('')
    const query = new URLSearchParams({ export_format: exportFormat })
    if (reportStartDate) query.set('date_debut', reportStartDate)
    if (reportEndDate) query.set('date_fin', reportEndDate)
    if (exportPieceId) query.set('piece', exportPieceId)
    if (exportUserId) query.set('utilisateur', exportUserId)
    if (exportMovementType) query.set('type_mouvement', exportMovementType)
    try {
      const response = await fetch(
        `/api/rapports/export/${exportType}/?${query.toString()}`,
        { credentials: 'include' },
      )
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || JSON.stringify(data))
      }
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = `${exportType}-${new Date().toISOString().slice(0, 10)}.${exportFormat}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function createSaleDraft(event) {
    event.preventDefault()
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(
        editingSaleId ? `/api/ventes/${editingSaleId}/` : '/api/ventes/',
        {
        method: editingSaleId ? 'PATCH' : 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
          client: saleClientId ? Number(saleClientId) : null,
          lignes: saleLines.map((line) => ({
            piece: Number(line.piece),
            quantite: Number(line.quantite),
          })),
        }),
        },
      )
      const data = await response.json()
      if (!response.ok) throw new Error(JSON.stringify(data))

      setSaleClientId('')
      setSaleLines([{ piece: '', quantite: '1' }])
      setEditingSaleId(null)
      await loadSales()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  function editSaleDraft(sale) {
    setEditingSaleId(sale.id)
    setSaleClientId(sale.client ? String(sale.client) : '')
    setSaleLines(sale.lignes.map((line) => ({
      piece: String(line.piece),
      quantite: String(line.quantite),
    })))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function changeSaleStatus(sale, action) {
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(`/api/ventes/${sale.id}/${action}/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRFToken': csrfToken },
      })
      const data = await response.json()
      if (!response.ok) throw new Error(JSON.stringify(data))
      await Promise.all([
        loadSales(),
        action === 'valider'
          ? loadDashboard(reportStartDate, reportEndDate)
          : Promise.resolve(),
      ])
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  function startSaleReturn(sale) {
      setSelectedReturnSale(sale)
      setReturnReason('')
      setReturnQuantities(Object.fromEntries(
        sale.lignes.map((line) => [line.id, '0']),
      ))
    }

  async function requestSaleReturn(event) {
      event.preventDefault()
      if (!selectedReturnSale) return
      const lines = selectedReturnSale.lignes
        .map((line) => ({
          ligne_vente: line.id,
          quantite: Number(returnQuantities[line.id] || 0),
        }))
        .filter((line) => line.quantite > 0)
      if (!lines.length) {
        setInventoryError('Indique au moins une quantité à retourner.')
        return
      }

      setInventoryError('')
      try {
        const csrfToken = await getCsrfToken()
        const response = await fetch('/api/retours-ventes/', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'Idempotency-Key': crypto.randomUUID(),
          },
          body: JSON.stringify({
            vente: selectedReturnSale.id,
            type_operation: 'RETOUR',
            motif: returnReason,
            lignes: lines,
          }),
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || JSON.stringify(data))
        setSelectedReturnSale(null)
        setReturnReason('')
        setReturnQuantities({})
        await loadSales()
      } catch (err) {
        setInventoryError(err.message)
      }
    }

  function requestSaleCancellation(sale) {
    setSelectedCancellationSale(sale)
    setCancellationReason('')
  }

  async function submitSaleCancellation(event) {
    event.preventDefault()
    if (!selectedCancellationSale) return
    const motif = cancellationReason.trim()
    if (!motif) {
      setInventoryError("Le motif d'annulation est obligatoire.")
      return
    }

    setInventoryError('')
    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(
        `/api/ventes/${selectedCancellationSale.id}/demander-annulation/`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'Idempotency-Key': crypto.randomUUID(),
          },
          body: JSON.stringify({ motif }),
        },
      )
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || JSON.stringify(data))
      setSelectedCancellationSale(null)
      setCancellationReason('')
      await loadSales()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function decideSaleReturn(returnId, decision, restock = false) {
      setInventoryError('')
      try {
        const csrfToken = await getCsrfToken()
        const response = await fetch(`/api/retours-ventes/${returnId}/${decision}/`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify(
            decision === 'autoriser' ? { remise_en_stock: restock } : {},
          ),
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || JSON.stringify(data))
        await Promise.all([
          loadSales(),
          loadDashboard(reportStartDate, reportEndDate),
        ])
      } catch (err) {
        setInventoryError(err.message)
      }
  }

  async function saveSupplier(event) {
    event.preventDefault()
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(
        editingSupplierId
          ? `/api/fournisseurs/${editingSupplierId}/`
          : '/api/fournisseurs/',
        {
          method: editingSupplierId ? 'PATCH' : 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify(supplierForm),
        },
      )
      const data = await response.json()
      if (!response.ok) throw new Error(JSON.stringify(data))

      setSupplierForm(emptySupplierForm)
      setEditingSupplierId(null)
      await loadSuppliers()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function createSupplierPurchase(event) {
      event.preventDefault()
      setInventoryError('')
      try {
        const csrfToken = await getCsrfToken()
        const response = await fetch('/api/achats-fournisseurs/', {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            fournisseur: Number(purchaseForm.fournisseur),
            lignes: purchaseForm.lignes.map((line) => ({
              piece: Number(line.piece),
              quantite: Number(line.quantite),
              prix_unitaire: line.prix_unitaire,
            })),
          }),
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || JSON.stringify(data))
        setPurchaseForm({
          fournisseur: '',
          lignes: [{ piece: '', quantite: '1', prix_unitaire: '' }],
        })
        await loadSuppliers()
      } catch (err) {
        setInventoryError(err.message)
      }
    }

  async function receiveSupplierPurchase(purchase) {
      if (!window.confirm(
        `Confirmer la réception physique de l'achat ${purchase.reference} ? Le stock sera augmenté.`,
      )) return
      setInventoryError('')
      try {
        const csrfToken = await getCsrfToken()
        const response = await fetch(
          `/api/achats-fournisseurs/${purchase.id}/recevoir/`,
          {
            method: 'POST',
            credentials: 'include',
            headers: { 'X-CSRFToken': csrfToken },
          },
        )
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || JSON.stringify(data))
        await Promise.all([loadSuppliers(), loadCatalog(), loadMovements()])
      } catch (err) {
        setInventoryError(err.message)
    }
  }

  function editSupplier(supplier) {
    setEditingSupplierId(supplier.id)
    setSupplierForm({
      nom: supplier.nom,
      telephone: supplier.telephone || '',
      email: supplier.email || '',
      adresse: supplier.adresse || '',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function toggleSupplierStatus(supplier) {
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(`/api/fournisseurs/${supplier.id}/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ actif: !supplier.actif }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(JSON.stringify(data))
      await loadSuppliers()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function saveClient(event) {
    event.preventDefault()
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(
        editingClientId ? `/api/clients/${editingClientId}/` : '/api/clients/',
        {
          method: editingClientId ? 'PATCH' : 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify(clientForm),
        },
      )
      const data = await response.json()
      if (!response.ok) throw new Error(JSON.stringify(data))

      setClientForm(emptyClientForm)
      setEditingClientId(null)
      await loadClients()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  function editClient(client) {
    setEditingClientId(client.id)
    setClientForm({
      nom: client.nom,
      telephone: client.telephone || '',
      adresse: client.adresse || '',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function toggleClientStatus(client) {
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(`/api/clients/${client.id}/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ actif: !client.actif }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(JSON.stringify(data))
      await loadClients()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function savePiece(event) {
    event.preventDefault()
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(
        editingPieceId ? `/api/pieces/${editingPieceId}/` : '/api/pieces/',
        {
          method: editingPieceId ? 'PATCH' : 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            ...pieceForm,
            categorie: Number(pieceForm.categorie),
            prix_achat: Number(pieceForm.prix_achat),
            prix_vente: Number(pieceForm.prix_vente),
            seuil_minimal: Number(pieceForm.seuil_minimal),
          }),
        },
      )
      const data = await response.json()

      if (!response.ok) {
        throw new Error(JSON.stringify(data))
      }

      setPieceForm(emptyPieceForm)
      setEditingPieceId(null)
      await loadCatalog()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function addCategory(event) {
    event.preventDefault()
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch('/api/categories/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ nom: categoryName }),
      })
      const data = await response.json()

      if (!response.ok) throw new Error(JSON.stringify(data))

      setCategoryName('')
      await loadCatalog()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  function editPiece(piece) {
    setEditingPieceId(piece.id)
    setPieceForm({
      reference: piece.reference,
      designation: piece.designation,
      categorie: String(piece.categorie),
      marque: piece.marque || '',
      modeles_compatibles: piece.modeles_compatibles || '',
      unite: piece.unite,
      prix_achat: piece.prix_achat,
      prix_vente: piece.prix_vente,
      seuil_minimal: String(piece.seuil_minimal),
      emplacement: piece.emplacement || '',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function togglePieceStatus(piece) {
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const response = await fetch(`/api/pieces/${piece.id}/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ actif: !piece.actif }),
      })
      const data = await response.json()

      if (!response.ok) throw new Error(JSON.stringify(data))
      await loadCatalog()
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  async function saveMovement(event) {
    event.preventDefault()
    setInventoryError('')

    try {
      const csrfToken = await getCsrfToken()
      const requestKey = movementRequestKey.current || crypto.randomUUID()
      movementRequestKey.current = requestKey
      const response = await fetch('/api/mouvements/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'Idempotency-Key': requestKey,
        },
        body: JSON.stringify({
          ...movementForm,
          piece: Number(movementForm.piece),
          quantite: Number(movementForm.quantite),
          prix_unitaire: Number(movementForm.prix_unitaire),
        }),
      })
      const data = await response.json()

      if (!response.ok) throw new Error(JSON.stringify(data))

      movementRequestKey.current = null
      setMovementForm(emptyMovementForm)
      await Promise.all([
        loadMovements(),
        loadDashboard(reportStartDate, reportEndDate),
      ])
    } catch (err) {
      setInventoryError(err.message)
    }
  }

  function updateMovementForm(changes) {
    movementRequestKey.current = null
    setMovementForm({ ...movementForm, ...changes })
  }

  function navigateToPage(nextPage) {
    if (nextPage === 'caisse' && !canAccessCash) {
      setInventoryError("Accès réservé à l'Administrateur et au Caissier.")
      return
    }

    setPage(nextPage)
    if (nextPage === 'dashboard') {
      loadDashboard(reportStartDate, reportEndDate)
    }
    if (nextPage === 'utilisateurs') loadUsers()
    if (nextPage === 'parametres-magasin') loadStoreSettings()
    if (nextPage === 'caisse') loadCashData()
    if (nextPage === 'pieces') loadCatalog()
    if (nextPage === 'stock') loadMovements()
    if (nextPage === 'clients') loadClients()
    if (nextPage === 'fournisseurs') loadSuppliers()
    if (nextPage === 'ventes') loadSales()
    if (nextPage === 'factures') loadInvoices()
    if (nextPage === 'rapports') {
      loadDashboard(reportStartDate, reportEndDate)
    }
  }

  const filteredPieces = pieces.filter((piece) =>
    [piece.reference, piece.designation, piece.marque, piece.categorie_nom]
      .join(' ')
      .toLowerCase()
      .includes(inventorySearch.trim().toLowerCase()),
  )
  const saleEstimate = saleLines.reduce((sum, line) => {
    const piece = pieces.find((item) => item.id === Number(line.piece))
    return sum + (piece ? Number(piece.prix_vente) * Number(line.quantite || 0) : 0)
  }, 0)

  const filteredUsers = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return users

    return users.filter((user) =>
      [
        user.username,
        user.first_name,
        user.last_name,
        user.email,
        ...(user.roles || []),
      ]
        .join(' ')
        .toLowerCase()
        .includes(term),
    )
  }, [users, search])

  const activeUsers = users.filter((user) => user.is_active).length
  const currentCashDate = new Date().toISOString().slice(0, 10)
  const todayCashClosure = cloturesCaisse.find(
    (closure) => closure.date_jour === currentCashDate,
  )
  const canManageUsers = Boolean(
    currentUser?.is_superuser
      || currentUser?.roles?.includes('Administrateur'),
  )
  const canAccessCash = Boolean(
    currentUser?.is_superuser
      || currentUser?.roles?.some((role) =>
        ['Administrateur', 'Caissier'].includes(role),
      ),
  )
  const canEditStoreSettings = Boolean(
  currentUser?.is_superuser
    || currentUser?.roles?.includes('Administrateur'),
)
  const canManageSupplierPurchases = Boolean(
    currentUser?.is_superuser
      || currentUser?.roles?.some((role) =>
        ['Administrateur', 'Responsable magasin', 'Gestionnaire de stock'].includes(role),
      ),
  )
  const userInitials = [currentUser?.first_name, currentUser?.last_name]
    .filter(Boolean)
    .map((name) => name[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() || currentUser?.username?.slice(0, 2).toUpperCase() || 'U'
  

  if (authLoading) {
    return (
      <div className="login-screen" role="status">
        Vérification de la session…
      </div>
    )
  }

  if (!currentUser) {
    return (
      <div className="login-screen">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="brand-icon login-logo">PA</div>

          <h1>PIÈCES AUTO</h1>
          <p>Connectez-vous à votre espace de gestion.</p>

          <label htmlFor="username">Nom d'utilisateur</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Votre identifiant"
            autoComplete="username"
            required
          />

          <label htmlFor="password">Mot de passe</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Votre mot de passe"
            autoComplete="current-password"
            required
          />

          {loginError && (
            <div className="error-message">{loginError}</div>
          )}

          <button type="submit" disabled={loginLoading}>
            {loginLoading ? 'Connexion en cours…' : 'Se connecter'}
          </button>

          <small>
            Accès réservé aux utilisateurs autorisés. Mot de passe oublié ?
            Contactez l’administrateur du magasin ; aucune récupération autonome
            n’est configurée.
          </small>
        </form>
      </div>
    )
  }

  return (
    <div className={`app-shell module-${page}`}>
      <aside className="sidebar border-r border-slate-800/60 bg-slate-950">
        <div className="brand">
          <div className="brand-icon">PA</div>
          <div>
            <strong>PIÈCES AUTO</strong>
            <span>Gestion & stock</span>
          </div>
        </div>

        <div className="menu-caption">MENU PRINCIPAL</div>
        <nav className="navigation">
          {navigation
            .filter((item) => item.id !== 'utilisateurs' || canManageUsers)
            .filter((item) => item.id !== 'caisse' || canAccessCash)
            .map((item) => (
            <button
              key={item.id}
              className={`nav-item transition-colors duration-200 ${page === item.id ? 'active' : ''}`}
              onClick={() => navigateToPage(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
              {item.id === 'utilisateurs' && (
                <span className="nav-arrow">›</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="help-icon">?</div>
          <div>
            <strong>Besoin d'aide ?</strong>
            <span>Consulte les informations du système.</span>
          </div>
        </div>
        <div className="sidebar-footer">Gestion des pièces détachées</div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Application</span>
            <span className="breadcrumb-separator">/</span>
            <strong>
              {navigation.find((item) => item.id === page)?.label}
            </strong>
          </div>
          <div className="topbar-right">
            <span className="system-status">
              <span className="status-dot" />
              Espace de gestion
            </span>
            <div className="avatar">{userInitials}</div>
            <div className="profile">
              <strong>
                {[currentUser.first_name, currentUser.last_name]
                  .filter(Boolean)
                  .join(' ') || currentUser.username}
              </strong>
              <span>{currentUser.roles?.join(', ') || 'Utilisateur'}</span>
            </div>
            <div className="profile-password-control">
              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setProfilePasswordOpen(!profilePasswordOpen)
                  setProfilePasswordForm({
                    current_password: '',
                    new_password: '',
                    confirm_password: '',
                  })
                  setProfilePasswordError('')
                  setProfilePasswordSuccess('')
                }}
              >
                Mon profil
              </button>
              {profilePasswordOpen && (
                <section className="profile-password-panel">
                  <div className="card-heading">
                    <div>
                      <h2>Changer mon mot de passe</h2>
                      <p>Votre mot de passe actuel est nécessaire.</p>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setProfilePasswordOpen(false)
                        setProfilePasswordForm({
                          current_password: '',
                          new_password: '',
                          confirm_password: '',
                        })
                      }}
                    >
                      Fermer
                    </button>
                  </div>
                  {profilePasswordError && (
                    <div className="error-message" role="alert">
                      {profilePasswordError}
                    </div>
                  )}
                  {profilePasswordSuccess && (
                    <div className="success-message" role="status">
                      {profilePasswordSuccess}
                    </div>
                  )}
                  <form className="inventory-form" onSubmit={changeOwnPassword}>
                    <label className="inventory-form-wide">
                      Mot de passe actuel
                      <input
                        type="password"
                        autoComplete="current-password"
                        required
                        value={profilePasswordForm.current_password}
                        onChange={(event) => setProfilePasswordForm({
                          ...profilePasswordForm,
                          current_password: event.target.value,
                        })}
                      />
                    </label>
                    <label>
                      Nouveau mot de passe
                      <input
                        type="password"
                        autoComplete="new-password"
                        required
                        value={profilePasswordForm.new_password}
                        onChange={(event) => setProfilePasswordForm({
                          ...profilePasswordForm,
                          new_password: event.target.value,
                        })}
                      />
                    </label>
                    <label>
                      Confirmer le nouveau mot de passe
                      <input
                        type="password"
                        autoComplete="new-password"
                        required
                        value={profilePasswordForm.confirm_password}
                        onChange={(event) => setProfilePasswordForm({
                          ...profilePasswordForm,
                          confirm_password: event.target.value,
                        })}
                      />
                    </label>
                    <div className="inventory-form-actions inventory-form-wide">
                      <button
                        className="primary-button"
                        type="submit"
                        disabled={profilePasswordSaving}
                      >
                        {profilePasswordSaving ? 'Enregistrement…' : 'Mettre à jour'}
                      </button>
                    </div>
                  </form>
                </section>
              )}
            </div>
            <button
              className="logout-button"
              onClick={handleLogout}
              title="Se déconnecter"
            >
              Déconnexion
            </button>
          </div>
        </header>

        <div className="page-content">
          {loginError && (
            <div className="error-message" role="alert">
              {loginError}
            </div>
          )}
          {page === 'dashboard' && (
            <>
              {inventoryError && (
                <div className="error-message" role="alert">
                  {inventoryError}
                </div>
              )}
              <div className="page-heading">
                <div>
                  <div className="eyebrow">VUE D'ENSEMBLE</div>
                  <h1>Tableau de bord</h1>
                  <p>Bienvenue dans votre espace de gestion.</p>
                </div>
                <span className="date-label">
                  <span>◷</span> Vue générale
                </span>
              </div>

              <form className="dashboard-filter" onSubmit={filterDashboard}>
                <label>
                  Du
                  <input
                    type="date"
                    value={reportStartDate}
                    onChange={(event) => setReportStartDate(event.target.value)}
                  />
                </label>
                <label>
                  Au
                  <input
                    type="date"
                    value={reportEndDate}
                    onChange={(event) => setReportEndDate(event.target.value)}
                  />
                </label>
                <button className="primary-button" type="submit">
                  Filtrer les ventes
                </button>
              </form>

              <section className="welcome-banner">
                <div>
                  <span className="banner-label">GESTION DU MAGASIN</span>
                  <h2>Toutes vos opérations, au même endroit.</h2>
                  <p>
                    Gérez vos pièces, suivez les mouvements de stock et
                    préparez vos opérations commerciales.
                  </p>
                  <button
                    className="banner-button"
                    onClick={() => navigateToPage('pieces')}
                  >
                    Accéder au catalogue <span>→</span>
                  </button>
                </div>
                <div className="banner-art" aria-hidden="true">
                  <div className="gear gear-one">⚙</div>
                  <div className="gear gear-two">⚙</div>
                  <div className="gear gear-three">⚙</div>
                </div>
              </section>

              <div className="section-heading">
                <div>
                  <h2>Vue d'ensemble</h2>
                  <p>Les indicateurs principaux de votre activité.</p>
                </div>
              </div>

              <section className="stats-grid">
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Références en stock</span>
                    <span className="stat-icon blue">▤</span>
                  </div>
                  <strong className="stat-number">
                    {dashboardData?.references_actives ?? '—'}
                  </strong>
                  <span className="stat-note">Pièces actives</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Stock faible</span>
                    <span className="stat-icon orange">⚠</span>
                  </div>
                  <strong className="stat-number">
                    {dashboardData?.stock_faible ?? '—'}
                  </strong>
                  <span className="stat-note">Références sous le seuil minimal</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>En rupture</span>
                    <span className="stat-icon purple">♙</span>
                  </div>
                  <strong className="stat-number">
                    {dashboardData?.ruptures ?? '—'}
                  </strong>
                  <span className="stat-note">Pièces en rupture</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Catégories</span>
                    <span className="stat-icon green">▦</span>
                  </div>
                  <strong className="stat-number">
                    {categories.length}
                  </strong>
                  <span className="stat-note">Catégories enregistrées</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Ventes validées</span>
                    <span className="stat-icon blue">▣</span>
                  </div>
                  <strong className="stat-number">
                    {dashboardData?.ventes_validees ?? '—'}
                  </strong>
                  <span className="stat-note">Pour la période sélectionnée</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Chiffre d'affaires</span>
                    <span className="stat-icon green">₣</span>
                  </div>
                  <strong className="stat-number stat-currency">
                    {dashboardData
                      ? Number(dashboardData.chiffre_affaires).toLocaleString('fr-FR')
                      : '—'}
                  </strong>
                  <span className="stat-note">Ventes validées, hors paiements</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Encaissements nets</span>
                    <span className="stat-icon green">₣</span>
                  </div>
                  <strong className="stat-number stat-currency">
                    {dashboardData
                      ? Number(dashboardData.montant_encaisse_net).toLocaleString('fr-FR')
                      : '—'}
                  </strong>
                  <span className="stat-note">Après remboursements exécutés</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Impayés</span>
                    <span className="stat-icon orange">₣</span>
                  </div>
                  <strong className="stat-number stat-currency">
                    {dashboardData
                      ? Number(dashboardData.impayes).toLocaleString('fr-FR')
                      : '—'}
                  </strong>
                  <span className="stat-note">Soldes restants des factures</span>
                </article>
              </section>

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Mouvements récents</h2>
                    <p>Dernières opérations de stock enregistrées.</p>
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>DATE</th>
                        <th>PIÈCE</th>
                        <th>TYPE</th>
                        <th>QUANTITÉ</th>
                        <th>MOTIF</th>
                        <th>UTILISATEUR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(dashboardData?.mouvements_recents || []).map((movement) => (
                        <tr key={movement.id}>
                          <td>{formatBusinessDateTime(movement.date)}</td>
                          <td>{movement.piece_reference}</td>
                          <td>{movement.type}</td>
                          <td>{movement.quantite}</td>
                          <td>{movement.motif}</td>
                          <td>{movement.utilisateur}</td>
                        </tr>
                      ))}
                      {dashboardData && !dashboardData.mouvements_recents.length && (
                        <tr>
                          <td colSpan="6" className="empty-state">
                            Aucun mouvement de stock.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="content-card quick-card">
                <div className="card-heading">
                  <div>
                    <h2>Accès rapides</h2>
                    <p>Retrouvez les principales rubriques.</p>
                  </div>
                </div>
                <div className="quick-grid">
                  {canManageUsers && (
                    <button onClick={() => navigateToPage('utilisateurs')}>
                      <span className="quick-icon purple">♙</span>
                      <span>
                        <strong>Utilisateurs et rôles</strong>
                        <small>Comptes et accès</small>
                      </span>
                      <span className="quick-arrow">→</span>
                    </button>
                  )}
                  <button onClick={() => navigateToPage('pieces')}>
                    <span className="quick-icon blue">▤</span>
                    <span>
                      <strong>Pièces détachées</strong>
                      <small>Catalogue du magasin</small>
                    </span>
                    <span className="quick-arrow">→</span>
                  </button>
                  <button onClick={() => navigateToPage('stock')}>
                    <span className="quick-icon orange">⇄</span>
                    <span>
                      <strong>Mouvements de stock</strong>
                      <small>Entrées et sorties</small>
                    </span>
                    <span className="quick-arrow">→</span>
                  </button>
                </div>
              </section>
            </>
          )}

          {page === 'rapports' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">ANALYSE DE L'ACTIVITÉ</div>
                  <h1>Rapports</h1>
                  <p>
                    Le chiffre d'affaires correspond aux ventes validées ; les
                    encaissements nets tiennent compte des remboursements exécutés.
                  </p>
                </div>
                <button
                  className="primary-button"
                  onClick={() => loadDashboard(reportStartDate, reportEndDate)}
                  disabled={inventoryLoading}
                >
                  Actualiser
                </button>
              </div>

              {inventoryError && (
                <div className="error-message" role="alert">
                  {inventoryError}
                  <button
                    type="button"
                    onClick={() => loadDashboard(reportStartDate, reportEndDate)}
                  >
                    Réessayer
                  </button>
                </div>
              )}

              <form className="dashboard-filter" onSubmit={filterDashboard}>
                <label>
                  Du
                  <input
                    type="date"
                    value={reportStartDate}
                    onChange={(event) => setReportStartDate(event.target.value)}
                  />
                </label>
                <label>
                  Au
                  <input
                    type="date"
                    value={reportEndDate}
                    onChange={(event) => setReportEndDate(event.target.value)}
                  />
                </label>
                <button className="primary-button" type="submit">
                  Appliquer la période
                </button>
              </form>

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Exporter les données</h2>
                    <p>
                      Télécharge un vrai fichier Excel ou PDF. La période sélectionnée
                      est appliquée aux données datées.
                    </p>
                  </div>
                </div>
                <div className="dashboard-filter">
                  <label>
                    Données
                    <select
                      value={exportType}
                      onChange={(event) => setExportType(event.target.value)}
                    >
                      <option value="indicateurs">Indicateurs</option>
                      <option value="factures">Factures</option>
                      <option value="ventes">Ventes</option>
                      <option value="encaissements">Encaissements / reçus</option>
                      <option value="remboursements">Remboursements</option>
                      <option value="stock">État du stock</option>
                      <option value="mouvements">Mouvements de stock</option>
                      <option value="retours">Retours et annulations</option>
                      <option value="achats-fournisseurs">Achats fournisseurs</option>
                    </select>
                  </label>
                  <label>
                    Format
                    <select
                      value={exportFormat}
                      onChange={(event) => setExportFormat(event.target.value)}
                    >
                      <option value="xlsx">Excel (.xlsx)</option>
                      <option value="pdf">PDF (.pdf)</option>
                    </select>
                  </label>
                  <label>
                    ID de pièce (facultatif)
                    <input
                      type="number"
                      min="1"
                      value={exportPieceId}
                      onChange={(event) => setExportPieceId(event.target.value)}
                    />
                  </label>
                  <label>
                    ID utilisateur (facultatif)
                    <input
                      type="number"
                      min="1"
                      value={exportUserId}
                      onChange={(event) => setExportUserId(event.target.value)}
                    />
                  </label>
                  <label>
                    Type de mouvement (facultatif)
                    <select
                      value={exportMovementType}
                      onChange={(event) => setExportMovementType(event.target.value)}
                    >
                      <option value="">Tous les types</option>
                      <option value="ENTREE">Entrée</option>
                      <option value="SORTIE">Sortie</option>
                      <option value="RETOUR">Retour</option>
                      <option value="CORRECTION">Correction</option>
                    </select>
                  </label>
                  <button
                    className="primary-button"
                    type="button"
                    onClick={downloadReportExport}
                  >
                    Télécharger l'export
                  </button>
                </div>
              </section>

              <section className="stats-grid">
                <article className="stat-card">
                  <div className="stat-top"><span>Références actives</span></div>
                  <strong className="stat-number">{dashboardData?.references_actives ?? '—'}</strong>
                </article>
                <article className="stat-card">
                  <div className="stat-top"><span>Stock faible</span></div>
                  <strong className="stat-number">{dashboardData?.stock_faible ?? '—'}</strong>
                </article>
                <article className="stat-card">
                  <div className="stat-top"><span>Ruptures</span></div>
                  <strong className="stat-number">{dashboardData?.ruptures ?? '—'}</strong>
                </article>
                <article className="stat-card">
                  <div className="stat-top"><span>Ventes validées</span></div>
                  <strong className="stat-number">{dashboardData?.ventes_validees ?? '—'}</strong>
                </article>
                <article className="stat-card">
                  <div className="stat-top"><span>Chiffre d'affaires</span></div>
                  <strong className="stat-number stat-currency">
                    {dashboardData
                      ? Number(dashboardData.chiffre_affaires).toLocaleString('fr-FR')
                      : '—'}
                  </strong>
                </article>
                <article className="stat-card">
                  <div className="stat-top"><span>Encaissements nets</span></div>
                  <strong className="stat-number stat-currency">
                    {dashboardData
                      ? Number(dashboardData.montant_encaisse_net).toLocaleString('fr-FR')
                      : '—'}
                  </strong>
                </article>
                <article className="stat-card">
                  <div className="stat-top"><span>Impayés</span></div>
                  <strong className="stat-number stat-currency">
                    {dashboardData
                      ? Number(dashboardData.impayes).toLocaleString('fr-FR')
                      : '—'}
                  </strong>
                </article>
              </section>

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Encaissements par moyen de paiement</h2>
                    <p>Seuls les remboursements exécutés sont déduits du montant brut.</p>
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>MODE</th>
                        <th>ENCAISSÉ BRUT</th>
                        <th>REMBOURSÉ</th>
                        <th>NET</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ['ESPECES', 'Espèces'],
                        ['MOBILE_MONEY', 'Mobile money'],
                        ['CARTE', 'Carte bancaire'],
                        ['VIREMENT', 'Virement'],
                        ['AUTRE', 'Autre'],
                      ].map(([mode, label]) => {
                        const amounts = dashboardData?.encaissements_par_mode?.[mode]
                        return (
                          <tr key={mode}>
                            <td>{label}</td>
                            <td>{amounts ? `${Number(amounts.encaisse_brut).toLocaleString('fr-FR')} FCFA` : '—'}</td>
                            <td>{amounts ? `${Number(amounts.rembourse).toLocaleString('fr-FR')} FCFA` : '—'}</td>
                            <td>{amounts ? `${Number(amounts.net).toLocaleString('fr-FR')} FCFA` : '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Mouvements récents</h2>
                    <p>{dashboardData?.mouvements_recents?.length ?? '—'} opération(s)</p>
                  </div>
                </div>
                {inventoryLoading ? (
                  <div className="loading-state">Chargement du rapport…</div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>DATE</th>
                          <th>PIÈCE</th>
                          <th>TYPE</th>
                          <th>QUANTITÉ</th>
                          <th>MOTIF</th>
                          <th>UTILISATEUR</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(dashboardData?.mouvements_recents || []).map((movement) => (
                          <tr key={movement.id}>
                            <td>{formatBusinessDateTime(movement.date)}</td>
                            <td>{movement.piece_reference}</td>
                            <td>{movement.type}</td>
                            <td>{movement.quantite}</td>
                            <td>{movement.motif}</td>
                            <td>{movement.utilisateur}</td>
                          </tr>
                        ))}
                        {dashboardData && !dashboardData.mouvements_recents.length && (
                          <tr>
                            <td colSpan="6" className="empty-state">
                              Aucun mouvement pour le moment.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}

          {page === 'pieces' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">INVENTAIRE</div>
                  <h1>Pièces détachées</h1>
                  <p>Catalogue, niveaux de stock et catégories.</p>
                </div>
                <button
                  className="primary-button"
                  onClick={loadCatalog}
                  disabled={inventoryLoading}
                >
                  Actualiser
                </button>
              </div>

              {inventoryError && (
                <div className="error-message" role="alert">
                  {inventoryError}
                </div>
              )}

              <section className="content-card inventory-form-card">
                <div className="card-heading">
                  <div>
                    <h2>{editingPieceId ? 'Modifier la pièce' : 'Nouvelle pièce'}</h2>
                    <p>La quantité disponible évolue uniquement via les mouvements.</p>
                  </div>
                </div>
                <form className="inventory-form" onSubmit={savePiece}>
                  <label>
                    Référence
                    <input
                      required
                      maxLength="50"
                      value={pieceForm.reference}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, reference: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Désignation
                    <input
                      required
                      maxLength="200"
                      value={pieceForm.designation}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, designation: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Catégorie
                    <select
                      required
                      value={pieceForm.categorie}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, categorie: event.target.value })
                      }
                    >
                      <option value="">Sélectionner</option>
                      {categories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.nom}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Marque
                    <input
                      value={pieceForm.marque}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, marque: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Prix d'achat
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      required
                      value={pieceForm.prix_achat}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, prix_achat: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Prix de vente
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      required
                      value={pieceForm.prix_vente}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, prix_vente: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Seuil minimal
                    <input
                      type="number"
                      min="0"
                      step="1"
                      required
                      value={pieceForm.seuil_minimal}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, seuil_minimal: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Unité
                    <input
                      required
                      value={pieceForm.unite}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, unite: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Emplacement
                    <input
                      value={pieceForm.emplacement}
                      onChange={(event) =>
                        setPieceForm({ ...pieceForm, emplacement: event.target.value })
                      }
                    />
                  </label>
                  <label className="inventory-form-wide">
                    Modèles compatibles
                    <textarea
                      rows="2"
                      value={pieceForm.modeles_compatibles}
                      onChange={(event) =>
                        setPieceForm({
                          ...pieceForm,
                          modeles_compatibles: event.target.value,
                        })
                      }
                    />
                  </label>
                  <div className="inventory-form-actions inventory-form-wide">
                    <button className="primary-button" type="submit">
                      {editingPieceId ? 'Enregistrer' : 'Ajouter la pièce'}
                    </button>
                    {editingPieceId && (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => {
                          setEditingPieceId(null)
                          setPieceForm(emptyPieceForm)
                        }}
                      >
                        Annuler
                      </button>
                    )}
                  </div>
                </form>
              </section>

              <section className="content-card inventory-form-card">
                <div className="card-heading">
                  <div>
                    <h2>Catégories</h2>
                    <p>{categories.length} catégorie(s) disponibles</p>
                  </div>
                </div>
                <form className="category-form" onSubmit={addCategory}>
                  <label htmlFor="new-category">Nom de la catégorie</label>
                  <input
                    id="new-category"
                    required
                    maxLength="100"
                    value={categoryName}
                    onChange={(event) => setCategoryName(event.target.value)}
                  />
                  <button className="primary-button" type="submit">
                    Ajouter
                  </button>
                </form>
              </section>

              <section className="content-card">
                <div className="card-heading users-card-heading">
                  <div>
                    <h2>Catalogue</h2>
                    <p>{filteredPieces.length} pièce(s) affichée(s)</p>
                  </div>
                  <label className="search-box">
                    <span>⌕</span>
                    <input
                      value={inventorySearch}
                      onChange={(event) => setInventorySearch(event.target.value)}
                      placeholder="Référence, désignation, marque..."
                    />
                  </label>
                </div>
                {inventoryLoading ? (
                  <div className="loading-state">Chargement du catalogue…</div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>RÉFÉRENCE / DÉSIGNATION</th>
                          <th>CATÉGORIE</th>
                          <th>STOCK</th>
                          <th>PRIX DE VENTE</th>
                          <th>STATUT</th>
                          <th>ACTIONS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredPieces.map((piece) => (
                          <tr key={piece.id}>
                            <td>
                              <strong>{piece.reference}</strong>
                              <small className="table-secondary">{piece.designation}</small>
                            </td>
                            <td>{piece.categorie_nom}</td>
                            <td>
                              {piece.quantite_stock} {piece.unite}
                              {piece.en_rupture
                                ? ' · Rupture'
                                : piece.stock_faible
                                  ? ' · Faible'
                                  : ''}
                            </td>
                            <td>{Number(piece.prix_vente).toLocaleString('fr-FR')}</td>
                            <td>{piece.actif ? 'Actif' : 'Inactif'}</td>
                            <td>
                              <div className="inventory-row-actions">
                                <button
                                  className="secondary-button"
                                  onClick={() => editPiece(piece)}
                                >
                                  Modifier
                                </button>
                                <button
                                  className="secondary-button"
                                  onClick={() => togglePieceStatus(piece)}
                                >
                                  {piece.actif ? 'Désactiver' : 'Réactiver'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                        {!filteredPieces.length && !inventoryLoading && (
                          <tr>
                            <td colSpan="6" className="empty-state">
                              Aucune pièce trouvée.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}

          {page === 'stock' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">INVENTAIRE</div>
                  <h1>Mouvements de stock</h1>
                  <p>Enregistrer une entrée, sortie, correction ou retour.</p>
                </div>
                <button
                  className="primary-button"
                  onClick={loadMovements}
                  disabled={inventoryLoading}
                >
                  Actualiser
                </button>
              </div>

              {inventoryError && (
                <div className="error-message" role="alert">
                  {inventoryError}
                </div>
              )}

              <section className="content-card inventory-form-card">
                <div className="card-heading">
                  <div>
                    <h2>Nouveau mouvement</h2>
                    <p>Les mouvements enregistrés ne peuvent pas être supprimés.</p>
                  </div>
                </div>
                <form className="inventory-form" onSubmit={saveMovement}>
                  <label>
                    Pièce
                    <select
                      required
                      value={movementForm.piece}
                      onChange={(event) =>
                        updateMovementForm({ piece: event.target.value })
                      }
                    >
                      <option value="">Sélectionner une pièce</option>
                      {pieces.filter((piece) => piece.actif).map((piece) => (
                        <option key={piece.id} value={piece.id}>
                          {piece.reference} · {piece.designation} ({piece.quantite_stock})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Type
                    <select
                      value={movementForm.type_mouvement}
                      onChange={(event) =>
                        updateMovementForm({ type_mouvement: event.target.value })
                      }
                    >
                      <option value="ENTREE">Entrée</option>
                      <option value="SORTIE">Sortie</option>
                      <option value="RETOUR">Retour</option>
                      <option value="CORRECTION">Correction (nouveau stock total)</option>
                    </select>
                  </label>
                  <label>
                    {movementForm.type_mouvement === 'CORRECTION'
                      ? 'Stock compté'
                      : 'Quantité'}
                    <input
                      type="number"
                      min={movementForm.type_mouvement === 'CORRECTION' ? '0' : '1'}
                      step="1"
                      required
                      value={movementForm.quantite}
                      onChange={(event) =>
                        updateMovementForm({ quantite: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Motif
                    <input
                      required
                      maxLength="255"
                      value={movementForm.motif}
                      onChange={(event) =>
                        updateMovementForm({ motif: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Prix unitaire
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={movementForm.prix_unitaire}
                      onChange={(event) =>
                        updateMovementForm({ prix_unitaire: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Référence du document
                    <input
                      value={movementForm.reference_document}
                      onChange={(event) =>
                        updateMovementForm({ reference_document: event.target.value })
                      }
                    />
                  </label>
                  <label className="inventory-form-wide">
                    Observation
                    <textarea
                      rows="2"
                      value={movementForm.observation}
                      onChange={(event) =>
                        updateMovementForm({ observation: event.target.value })
                      }
                    />
                  </label>
                  <div className="inventory-form-actions inventory-form-wide">
                    <button className="primary-button" type="submit">
                      Enregistrer le mouvement
                    </button>
                  </div>
                </form>
              </section>

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Historique</h2>
                    <p>{movements.length} mouvement(s) chargés</p>
                  </div>
                </div>
                {inventoryLoading ? (
                  <div className="loading-state">Chargement des mouvements…</div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>DATE</th>
                          <th>PIÈCE</th>
                          <th>TYPE</th>
                          <th>QUANTITÉ</th>
                          <th>MOTIF</th>
                          <th>DOCUMENT</th>
                          <th>UTILISATEUR</th>
                        </tr>
                      </thead>
                      <tbody>
                        {movements.map((movement) => (
                          <tr key={movement.id}>
                            <td>
                              {formatBusinessDateTime(movement.date_mouvement)}
                            </td>
                            <td>
                              {movement.piece_reference} · {movement.piece_designation}
                            </td>
                            <td>{movement.type_mouvement}</td>
                            <td>{movement.quantite}</td>
                            <td>{movement.motif}</td>
                            <td>{movement.reference_document || '—'}</td>
                            <td>{movement.utilisateur_nom}</td>
                          </tr>
                        ))}
                        {!movements.length && !inventoryLoading && (
                          <tr>
                            <td colSpan="7" className="empty-state">
                              Aucun mouvement enregistré.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}

          {page === 'clients' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">RELATION CLIENT</div>
                  <h1>Clients</h1>
                  <p>Coordonnées des clients enregistrés dans le magasin.</p>
                </div>
                <button
                  className="primary-button"
                  onClick={loadClients}
                  disabled={inventoryLoading}
                >
                  Actualiser
                </button>
              </div>

              {inventoryError && (
                <div className="error-message" role="alert">
                  {inventoryError}
                </div>
              )}

              <section className="content-card inventory-form-card">
                <div className="card-heading">
                  <div>
                    <h2>{editingClientId ? 'Modifier le client' : 'Nouveau client'}</h2>
                    <p>Le client reste facultatif pour une vente comptant.</p>
                  </div>
                </div>
                <form className="inventory-form" onSubmit={saveClient}>
                  <label>
                    Nom ou raison sociale
                    <input
                      required
                      maxLength="200"
                      value={clientForm.nom}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, nom: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Téléphone
                    <input
                      type="tel"
                      maxLength="30"
                      value={clientForm.telephone}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, telephone: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Adresse
                    <input
                      value={clientForm.adresse}
                      onChange={(event) =>
                        setClientForm({ ...clientForm, adresse: event.target.value })
                      }
                    />
                  </label>
                  <div className="inventory-form-actions inventory-form-wide">
                    <button className="primary-button" type="submit">
                      {editingClientId ? 'Enregistrer' : 'Ajouter le client'}
                    </button>
                    {editingClientId && (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => {
                          setEditingClientId(null)
                          setClientForm(emptyClientForm)
                        }}
                      >
                        Annuler
                      </button>
                    )}
                  </div>
                </form>
              </section>

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Répertoire clients</h2>
                    <p>{clients.length} client(s)</p>
                  </div>
                </div>
                {inventoryLoading ? (
                  <div className="loading-state">Chargement des clients…</div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>NOM / RAISON SOCIALE</th>
                          <th>TÉLÉPHONE</th>
                          <th>ADRESSE</th>
                          <th>STATUT</th>
                          <th>ACTIONS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {clients.map((client) => (
                          <tr key={client.id}>
                            <td>{client.nom}</td>
                            <td>{client.telephone || '—'}</td>
                            <td>{client.adresse || '—'}</td>
                            <td>{client.actif ? 'Actif' : 'Inactif'}</td>
                            <td>
                              <div className="inventory-row-actions">
                                <button
                                  className="secondary-button"
                                  onClick={() => editClient(client)}
                                >
                                  Modifier
                                </button>
                                <button
                                  className="secondary-button"
                                  onClick={() => toggleClientStatus(client)}
                                >
                                  {client.actif ? 'Désactiver' : 'Réactiver'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                        {!clients.length && !inventoryLoading && (
                          <tr>
                            <td colSpan="5" className="empty-state">
                              Aucun client enregistré.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}

          {page === 'fournisseurs' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">PARTENAIRES</div>
                  <h1>Fournisseurs</h1>
                  <p>Achats enregistrés et réceptions réelles historisées.</p>
                </div>
                <button
                  className="primary-button"
                  onClick={loadSuppliers}
                  disabled={inventoryLoading}
                >
                  Actualiser
                </button>
              </div>

              {inventoryError && (
                <div className="error-message" role="alert">
                  {inventoryError}
                </div>
              )}

              <section className="content-card inventory-form-card">
                <div className="card-heading">
                  <div>
                    <h2>{editingSupplierId ? 'Modifier le fournisseur' : 'Nouveau fournisseur'}</h2>
                    <p>Les commandes, dettes et paiements fournisseurs ne sont pas inclus.</p>
                  </div>
                </div>
                <form className="inventory-form" onSubmit={saveSupplier}>
                  <label>
                    Nom ou raison sociale
                    <input
                      required
                      maxLength="200"
                      value={supplierForm.nom}
                      onChange={(event) =>
                        setSupplierForm({ ...supplierForm, nom: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Téléphone
                    <input
                      type="tel"
                      maxLength="30"
                      value={supplierForm.telephone}
                      onChange={(event) =>
                        setSupplierForm({ ...supplierForm, telephone: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Adresse e-mail
                    <input
                      type="email"
                      value={supplierForm.email}
                      onChange={(event) =>
                        setSupplierForm({ ...supplierForm, email: event.target.value })
                      }
                    />
                  </label>
                  <label className="inventory-form-wide">
                    Adresse
                    <textarea
                      rows="2"
                      value={supplierForm.adresse}
                      onChange={(event) =>
                        setSupplierForm({ ...supplierForm, adresse: event.target.value })
                      }
                    />
                  </label>
                  <div className="inventory-form-actions inventory-form-wide">
                    <button className="primary-button" type="submit">
                      {editingSupplierId ? 'Enregistrer' : 'Ajouter le fournisseur'}
                    </button>
                    {editingSupplierId && (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => {
                          setEditingSupplierId(null)
                          setSupplierForm(emptySupplierForm)
                        }}
                      >
                        Annuler
                      </button>
                    )}
                  </div>
                </form>
              </section>

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Répertoire fournisseurs</h2>
                    <p>{suppliers.length} fournisseur(s)</p>
                  </div>
                </div>
                {inventoryLoading ? (
                  <div className="loading-state">Chargement des fournisseurs…</div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>NOM / RAISON SOCIALE</th>
                          <th>TÉLÉPHONE</th>
                          <th>E-MAIL</th>
                          <th>ADRESSE</th>
                          <th>STATUT</th>
                          <th>ACTIONS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {suppliers.map((supplier) => (
                          <tr key={supplier.id}>
                            <td>{supplier.nom}</td>
                            <td>{supplier.telephone || '—'}</td>
                            <td>{supplier.email || '—'}</td>
                            <td>{supplier.adresse || '—'}</td>
                            <td>{supplier.actif ? 'Actif' : 'Inactif'}</td>
                            <td>
                              <div className="inventory-row-actions">
                                <button
                                  className="secondary-button"
                                  onClick={() => editSupplier(supplier)}
                                >
                                  Modifier
                                </button>
                                <button
                                  className="secondary-button"
                                  onClick={() => toggleSupplierStatus(supplier)}
                                >
                                  {supplier.actif ? 'Désactiver' : 'Réactiver'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                        {!suppliers.length && !inventoryLoading && (
                          <tr>
                            <td colSpan="6" className="empty-state">
                              Aucun fournisseur enregistré.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {canManageSupplierPurchases && (
                <section className="content-card inventory-form-card">
                  <div className="card-heading">
                    <div>
                      <h2>Enregistrer un achat fournisseur</h2>
                      <p>
                        Cet enregistrement ne modifie pas le stock. La réception
                        physique doit être confirmée séparément.
                      </p>
                    </div>
                  </div>
                  <form className="inventory-form" onSubmit={createSupplierPurchase}>
                    <label>
                      Fournisseur
                      <select
                        required
                        value={purchaseForm.fournisseur}
                        onChange={(event) => setPurchaseForm({
                          ...purchaseForm,
                          fournisseur: event.target.value,
                        })}
                      >
                        <option value="">Sélectionner un fournisseur</option>
                        {suppliers.filter((supplier) => supplier.actif).map((supplier) => (
                          <option key={supplier.id} value={supplier.id}>{supplier.nom}</option>
                        ))}
                      </select>
                    </label>
                    <div className="sale-lines inventory-form-wide">
                      {purchaseForm.lignes.map((line, index) => (
                        <div className="sale-line" key={`purchase-line-${index}`}>
                          <label>
                            Pièce
                            <select
                              required
                              value={line.piece}
                              onChange={(event) => setPurchaseForm({
                                ...purchaseForm,
                                lignes: purchaseForm.lignes.map((item, lineIndex) =>
                                  lineIndex === index
                                    ? { ...item, piece: event.target.value }
                                    : item,
                                ),
                              })}
                            >
                              <option value="">Sélectionner une pièce</option>
                              {pieces.filter((piece) => piece.actif).map((piece) => (
                                <option key={piece.id} value={piece.id}>
                                  {piece.reference} · {piece.designation}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Quantité
                            <input
                              type="number"
                              min="1"
                              required
                              value={line.quantite}
                              onChange={(event) => setPurchaseForm({
                                ...purchaseForm,
                                lignes: purchaseForm.lignes.map((item, lineIndex) =>
                                  lineIndex === index
                                    ? { ...item, quantite: event.target.value }
                                    : item,
                                ),
                              })}
                            />
                          </label>
                          <label>
                            Prix d'achat unitaire
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              required
                              value={line.prix_unitaire}
                              onChange={(event) => setPurchaseForm({
                                ...purchaseForm,
                                lignes: purchaseForm.lignes.map((item, lineIndex) =>
                                  lineIndex === index
                                    ? { ...item, prix_unitaire: event.target.value }
                                    : item,
                                ),
                              })}
                            />
                          </label>
                          {purchaseForm.lignes.length > 1 && (
                            <button
                              className="secondary-button"
                              type="button"
                              onClick={() => setPurchaseForm({
                                ...purchaseForm,
                                lignes: purchaseForm.lignes.filter(
                                  (_, lineIndex) => lineIndex !== index,
                                ),
                              })}
                            >
                              Retirer
                            </button>
                          )}
                        </div>
                      ))}
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => setPurchaseForm({
                          ...purchaseForm,
                          lignes: [
                            ...purchaseForm.lignes,
                            { piece: '', quantite: '1', prix_unitaire: '' },
                          ],
                        })}
                      >
                        Ajouter une pièce
                      </button>
                    </div>
                    <div className="inventory-form-actions inventory-form-wide">
                      <button className="primary-button" type="submit">
                        Enregistrer l'achat
                      </button>
                    </div>
                  </form>
                </section>
              )}

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Historique des achats et réceptions</h2>
                    <p>{supplierPurchases.length} achat(s) enregistré(s)</p>
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>RÉFÉRENCE / CRÉATION</th>
                        <th>FOURNISSEUR</th>
                        <th>ARTICLES</th>
                        <th>TOTAL ACHAT</th>
                        <th>STATUT / RÉCEPTION</th>
                        {canManageSupplierPurchases && <th>ACTIONS</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {supplierPurchases.map((purchase) => (
                        <tr key={purchase.id}>
                          <td>
                            <strong>{purchase.reference}</strong>
                            <small className="table-secondary">
                              {formatBusinessDateTime(purchase.date_creation)}
                            </small>
                          </td>
                          <td>{purchase.fournisseur_nom}</td>
                          <td>
                            {purchase.lignes.map((line) => (
                              <span className="sale-item" key={line.id}>
                                {line.quantite} × {line.reference_piece}
                              </span>
                            ))}
                          </td>
                          <td>{Number(purchase.montant_total).toLocaleString('fr-FR')} FCFA</td>
                          <td>
                            {purchase.statut}
                            {purchase.date_reception && (
                              <small className="table-secondary">
                                Reçu le {formatBusinessDateTime(purchase.date_reception)} · {purchase.recu_par_nom}
                              </small>
                            )}
                          </td>
                          {canManageSupplierPurchases && (
                            <td>
                              {purchase.statut === 'BROUILLON' ? (
                                <button
                                  className="primary-button"
                                  onClick={() => receiveSupplierPurchase(purchase)}
                                >
                                  Confirmer la réception
                                </button>
                              ) : '—'}
                            </td>
                          )}
                        </tr>
                      ))}
                      {!supplierPurchases.length && (
                        <tr>
                          <td colSpan={canManageSupplierPurchases ? 6 : 5} className="empty-state">
                            Aucun achat fournisseur enregistré.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}

          {page === 'ventes' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">OPÉRATIONS COMMERCIALES</div>
                  <h1>Ventes</h1>
                  <p>Les ventes restent en brouillon jusqu'à leur validation.</p>
                </div>
                <button
                  className="primary-button"
                  onClick={loadSales}
                  disabled={inventoryLoading}
                >
                  Actualiser
                </button>
              </div>

              {inventoryError && (
                <div className="error-message" role="alert">
                  {inventoryError}
                </div>
              )}

              <section className="content-card inventory-form-card">
                <div className="card-heading">
                  <div>
                    <h2>{editingSaleId ? 'Modifier le brouillon' : 'Nouvelle vente'}</h2>
                    <p>Le stock ne change qu'au moment de valider la vente.</p>
                  </div>
                </div>
                <form className="inventory-form" onSubmit={createSaleDraft}>
                  <label>
                    Client (facultatif)
                    <select
                      value={saleClientId}
                      onChange={(event) => setSaleClientId(event.target.value)}
                    >
                      <option value="">Vente comptant sans client</option>
                      {clients.filter((client) => client.actif).map((client) => (
                        <option key={client.id} value={client.id}>
                          {client.nom}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="sale-lines inventory-form-wide">
                    {saleLines.map((line, index) => (
                      <div className="sale-line" key={`sale-line-${index}`}>
                        <label>
                          Pièce
                          <select
                            required
                            value={line.piece}
                            onChange={(event) =>
                              setSaleLines(saleLines.map((current, lineIndex) =>
                                lineIndex === index
                                  ? { ...current, piece: event.target.value }
                                  : current,
                              ))
                            }
                          >
                            <option value="">Référence ou désignation</option>
                            {pieces.filter((piece) => piece.actif).map((piece) => (
                              <option key={piece.id} value={piece.id}>
                                {piece.reference} · {piece.designation} · stock {piece.quantite_stock}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Quantité
                          <input
                            type="number"
                            min="1"
                            required
                            value={line.quantite}
                            onChange={(event) =>
                              setSaleLines(saleLines.map((current, lineIndex) =>
                                lineIndex === index
                                  ? { ...current, quantite: event.target.value }
                                  : current,
                              ))
                            }
                          />
                        </label>
                        <span className="sale-line-price">
                          {(() => {
                            const piece = pieces.find((item) => item.id === Number(line.piece))
                            return piece
                              ? `${Number(piece.prix_vente).toLocaleString('fr-FR')} / unité`
                              : 'Prix catalogue'
                          })()}
                        </span>
                        {saleLines.length > 1 && (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() =>
                              setSaleLines(saleLines.filter((_, lineIndex) => lineIndex !== index))
                            }
                            title="Retirer cette ligne"
                            aria-label={`Retirer la ligne ${index + 1}`}
                          >
                            Retirer
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => setSaleLines([...saleLines, { piece: '', quantite: '1' }])}
                    >
                      Ajouter une ligne
                    </button>
                  </div>

                  <div className="sale-total inventory-form-wide">
                    <span>Total estimé</span>
                    <strong>{saleEstimate.toLocaleString('fr-FR')}</strong>
                  </div>
                  <div className="inventory-form-actions inventory-form-wide">
                    <button className="primary-button" type="submit">
                      {editingSaleId ? 'Enregistrer les modifications' : 'Enregistrer le brouillon'}
                    </button>
                    {editingSaleId && (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => {
                          setEditingSaleId(null)
                          setSaleClientId('')
                          setSaleLines([{ piece: '', quantite: '1' }])
                        }}
                      >
                        Annuler la modification
                      </button>
                    )}
                  </div>
                </form>
              </section>

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Historique des ventes</h2>
                    <p>{sales.length} vente(s)</p>
                  </div>
                </div>
                {inventoryLoading ? (
                  <div className="loading-state">Chargement des ventes…</div>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>RÉFÉRENCE / DATE</th>
                          <th>CLIENT</th>
                          <th>ARTICLES</th>
                          <th>TOTAL</th>
                          <th>STATUT</th>
                          <th>ACTIONS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sales.map((sale) => (
                          <tr key={sale.id}>
                            <td>
                              <strong>{sale.reference}</strong>
                              <small className="table-secondary">
                                {formatBusinessDateTime(sale.date_creation)}
                              </small>
                            </td>
                            <td>{sale.client_nom || 'Vente comptant'}</td>
                            <td>
                              {sale.lignes.map((line) => (
                                <span className="sale-item" key={line.id}>
                                  {line.quantite} × {line.reference_piece}
                                </span>
                              ))}
                            </td>
                            <td>{Number(sale.total).toLocaleString('fr-FR')}</td>
                            <td>{sale.statut}</td>
                            <td>
                              {sale.statut === 'BROUILLON' ? (
                                <div className="inventory-row-actions">
                                  <button
                                    className="secondary-button"
                                    onClick={() => editSaleDraft(sale)}
                                  >
                                    Modifier
                                  </button>
                                  <button
                                    className="primary-button"
                                    onClick={() => changeSaleStatus(sale, 'valider')}
                                  >
                                    Valider
                                  </button>
                                  <button
                                    className="secondary-button"
                                    onClick={() => changeSaleStatus(sale, 'annuler')}
                                  >
                                    Annuler
                                  </button>
                                </div>
                              ) : sale.statut === 'VALIDEE' ? (
                                <div className="inventory-row-actions">
                                  <button
                                    className="secondary-button"
                                    onClick={() => startSaleReturn(sale)}
                                    disabled={saleReturns.some(
                                      (record) =>
                                        record.vente === sale.id
                                        && record.statut === 'EN_ATTENTE',
                                    )}
                                  >
                                    Demander un retour
                                  </button>
                                  <button
                                    className="secondary-button"
                                    onClick={() => requestSaleCancellation(sale)}
                                    disabled={saleReturns.some(
                                      (record) => record.vente === sale.id,
                                    )}
                                  >
                                    Demander l'annulation
                                  </button>
                                </div>
                              ) : '—'}
                            </td>
                          </tr>
                        ))}
                        {!sales.length && !inventoryLoading && (
                          <tr>
                            <td colSpan="6" className="empty-state">
                              Aucune vente enregistrée.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {selectedCancellationSale && (
                <section className="content-card inventory-form-card">
                  <div className="card-heading">
                    <div>
                      <h2>Demander l'annulation · {selectedCancellationSale.reference}</h2>
                      <p>
                        La vente validée et sa facture seront conservées. La demande
                        doit être autorisée par un Administrateur; les paiements
                        reçus seront régularisés séparément.
                      </p>
                    </div>
                  </div>
                  <form className="inventory-form" onSubmit={submitSaleCancellation}>
                    <label className="inventory-form-wide">
                      Motif de l'annulation
                      <textarea
                        required
                        value={cancellationReason}
                        onChange={(event) => setCancellationReason(event.target.value)}
                      />
                    </label>
                    <div className="inventory-form-actions inventory-form-wide">
                      <button className="primary-button" type="submit">
                        Enregistrer la demande
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => setSelectedCancellationSale(null)}
                      >
                        Fermer
                      </button>
                    </div>
                  </form>
                </section>
              )}

              {selectedReturnSale && (
                <section className="content-card inventory-form-card">
                  <div className="card-heading">
                    <div>
                      <h2>Demander le retour · {selectedReturnSale.reference}</h2>
                      <p>
                        La demande doit être autorisée par un Administrateur.
                        Le remboursement financier, s’il y a lieu, fera l’objet
                        d’une confirmation séparée.
                      </p>
                    </div>
                  </div>
                  <form className="inventory-form" onSubmit={requestSaleReturn}>
                    {selectedReturnSale.lignes.map((line) => {
                      const previouslyReturned = saleReturns
                        .filter(
                          (record) =>
                            record.vente === selectedReturnSale.id
                            && record.statut !== 'REFUSE',
                        )
                        .flatMap((record) => record.lignes)
                        .filter((returned) => returned.ligne_vente === line.id)
                        .reduce((total, returned) => total + returned.quantite, 0)
                      const remaining = Math.max(line.quantite - previouslyReturned, 0)
                      return (
                        <label key={line.id}>
                          {line.reference_piece} · {line.designation} · {remaining} restante(s)
                          <input
                            type="number"
                            min="0"
                            max={remaining}
                            value={returnQuantities[line.id] || '0'}
                            onChange={(event) => setReturnQuantities({
                              ...returnQuantities,
                              [line.id]: event.target.value,
                            })}
                            disabled={remaining === 0}
                          />
                        </label>
                      )
                    })}
                    <label className="inventory-form-wide">
                      Motif du retour
                      <textarea
                        required
                        value={returnReason}
                        onChange={(event) => setReturnReason(event.target.value)}
                      />
                    </label>
                    <div className="inventory-form-actions inventory-form-wide">
                      <button className="primary-button" type="submit">
                        Enregistrer la demande
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => setSelectedReturnSale(null)}
                      >
                        Fermer
                      </button>
                    </div>
                  </form>
                </section>
              )}

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Historique des retours et annulations</h2>
                    <p>
                      Une autorisation ne confirme pas l’exécution d’un remboursement.
                    </p>
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>RÉFÉRENCE / DATE</th>
                        <th>VENTE</th>
                        <th>TYPE / MOTIF</th>
                        <th>ARTICLES / MONTANT</th>
                        <th>DEMANDEUR / DÉCISION</th>
                        <th>STATUT</th>
                        {canEditStoreSettings && <th>ACTIONS ADMIN</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {saleReturns.map((record) => (
                        <tr key={record.id}>
                          <td>
                            <strong>{record.reference}</strong>
                            <small className="table-secondary">
                              {formatBusinessDateTime(record.date_demande)}
                            </small>
                          </td>
                          <td>{record.vente_reference}</td>
                          <td>
                            {record.type_operation === 'ANNULATION' ? 'Annulation' : 'Retour'}
                            <small className="table-secondary">{record.motif}</small>
                          </td>
                          <td>
                            {record.lignes.map((line) => (
                              <span className="sale-item" key={line.id}>
                                {line.quantite} × {line.reference_piece}
                              </span>
                            ))}
                            <strong>{Number(record.montant_total).toLocaleString('fr-FR')} FCFA</strong>
                          </td>
                          <td>
                            {record.demande_par_nom}
                            {record.autorise_par_nom && (
                              <small className="table-secondary">
                                Décision : {record.autorise_par_nom}
                              </small>
                            )}
                          </td>
                          <td>
                            {record.statut}
                            {record.statut === 'AUTORISE' && (
                              <small className="table-secondary">
                                {record.remise_en_stock
                                  ? 'Remis en stock'
                                  : 'Non remis en stock'}
                              </small>
                            )}
                          </td>
                          {canEditStoreSettings && (
                            <td>
                              {record.statut === 'EN_ATTENTE' ? (
                                <div className="inventory-row-actions">
                                  <button
                                    className="primary-button"
                                    onClick={() => decideSaleReturn(record.id, 'autoriser', true)}
                                  >
                                    Autoriser + stock
                                  </button>
                                  <button
                                    className="secondary-button"
                                    onClick={() => decideSaleReturn(record.id, 'autoriser', false)}
                                  >
                                    Autoriser sans stock
                                  </button>
                                  <button
                                    className="secondary-button"
                                    onClick={() => decideSaleReturn(record.id, 'refuser')}
                                  >
                                    Refuser
                                  </button>
                                </div>
                              ) : '—'}
                            </td>
                          )}
                        </tr>
                      ))}
                      {!saleReturns.length && (
                        <tr>
                          <td colSpan={canEditStoreSettings ? 7 : 6} className="empty-state">
                            Aucun retour ou demande d'annulation enregistré.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
          
          {page === 'caisse' && canAccessCash && (
            selectedReceipt ? (
              <section className="receipt-print-area">
                <div className="invoice-actions non-printable">
                  <button
                    className="secondary-button"
                    onClick={() => setSelectedReceipt(null)}
                  >
                    Retour à la caisse
                  </button>
                  <button
                    className="primary-button"
                    onClick={() => window.print()}
                    disabled={!storeSettings}
                  >
                    Imprimer le reçu
                  </button>
                </div>
                <article className="invoice-paper receipt-paper">
                  <header className="invoice-heading">
                    <div>
                      {selectedReceipt.magasin.logo && (
                        <img
                          className="invoice-store-logo"
                          src={selectedReceipt.magasin.logo}
                          alt={`Logo ${selectedReceipt.magasin.nom_magasin}`}
                        />
                      )}
                      <strong>{selectedReceipt.magasin.nom_magasin}</strong>
                      {selectedReceipt.magasin.adresse && <p>{selectedReceipt.magasin.adresse}</p>}
                      {selectedReceipt.magasin.telephone && <p>{selectedReceipt.magasin.telephone}</p>}
                      {selectedReceipt.magasin.email && <p>{selectedReceipt.magasin.email}</p>}
                    </div>
                    <div className="invoice-number">
                      <span>REÇU DE PAIEMENT</span>
                      <strong>{selectedReceipt.encaissement.reference}</strong>
                    </div>
                  </header>
                  <div className="invoice-meta">
                    <p>
                      <span>Date et heure</span>
                      {formatBusinessDateTime(selectedReceipt.encaissement.date_encaissement)}
                    </p>
                    <p>
                      <span>Facture</span>
                      {selectedReceipt.encaissement.facture_reference}
                    </p>
                    <p>
                      <span>Client</span>
                      {selectedReceipt.encaissement.client_nom}
                    </p>
                  </div>
                  <div className="receipt-amount">
                    <span>Montant reçu</span>
                    <strong>
                      {Number(selectedReceipt.encaissement.montant).toLocaleString('fr-FR')} FCFA
                    </strong>
                  </div>
                  <div className="receipt-meta">
                    <p>
                      <span>Mode de paiement</span>
                      {selectedReceipt.encaissement.mode_paiement_libelle}
                    </p>
                    <p>
                      <span>Solde après ce paiement</span>
                      {Number(selectedReceipt.solde_restant_apres).toLocaleString('fr-FR')} FCFA
                    </p>
                    <p>
                      <span>Encaissé par</span>
                      {selectedReceipt.encaissement.encaisse_par_nom}
                    </p>
                  </div>
                  {selectedReceipt.magasin.pied_de_page && (
                    <footer className="invoice-footer">
                      {selectedReceipt.magasin.pied_de_page}
                    </footer>
                  )}
                </article>
              </section>
            ) : (
  <>
    <div className="page-heading">
      <div>
        <div className="eyebrow">GESTION FINANCIÈRE</div>
        <h1>Caisse</h1>
        <p>Suivi des paiements, des factures impayées et des encaissements.</p>
      </div>
      <button
        className="primary-button"
        onClick={loadCashData}
        disabled={inventoryLoading}
      >
        Actualiser
      </button>
    </div>

    {inventoryError && (
      <div className="error-message" role="alert">
        {inventoryError}
      </div>
    )}

    <div className="stats-grid">
      <article className="stat-card">
        <span>Factures à régler</span>
        <strong>
          {cashInvoices.filter((invoice) => Number(invoice.solde_restant) > 0).length}
        </strong>
      </article>

      <article className="stat-card">
        <span>Montant restant</span>
        <strong>
          {cashInvoices.reduce(
            (total, invoice) => total + Number(invoice.solde_restant || 0),
            0,
          ).toLocaleString('fr-FR')} FCFA
        </strong>
      </article>

      <article className="stat-card">
        <span>Total encaissé</span>
        <strong>
          {cashInvoices.reduce(
            (total, invoice) => total + Number(invoice.total_encaisse || 0),
            0,
          ).toLocaleString('fr-FR')} FCFA
        </strong>
      </article>
    </div>

    {selectedCashInvoice && (
      <section className="content-card inventory-form-card">
        <div className="card-heading">
          <div>
            <h2>Enregistrer un encaissement</h2>
            <p>
              Facture : {selectedCashInvoice.facture_reference}
              {' · '}
              Solde restant : {Number(selectedCashInvoice.solde_restant).toLocaleString('fr-FR')} FCFA
            </p>
          </div>
        </div>

        <form className="inventory-form" onSubmit={savePayment}>
          <label>
            Montant à encaisser (FCFA)
            <input
              type="number"
              min="0.01"
              max={selectedCashInvoice.solde_restant}
              step="0.01"
              required
              value={paymentForm.montant}
              onChange={(event) =>
                setPaymentForm({ ...paymentForm, montant: event.target.value })
              }
              disabled={paymentSubmitting || Boolean(todayCashClosure?.date_cloture)}
            />
          </label>

          <label>
            Mode de paiement
            <select
              value={paymentForm.mode_paiement}
              onChange={(event) =>
                setPaymentForm({ ...paymentForm, mode_paiement: event.target.value })
              }
              disabled={paymentSubmitting || Boolean(todayCashClosure?.date_cloture)}
            >
              <option value="ESPECES">Espèces</option>
              <option value="MOBILE_MONEY">Mobile Money</option>
              <option value="CARTE">Carte bancaire</option>
              <option value="VIREMENT">Virement</option>
              <option value="AUTRE">Autre</option>
            </select>
          </label>

          <div className="inventory-form-actions inventory-form-wide">
            <button
              className="primary-button"
              type="submit"
              disabled={paymentSubmitting || Boolean(todayCashClosure?.date_cloture)}
            >
              {paymentSubmitting ? 'Enregistrement...' : "Confirmer l'encaissement"}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                setSelectedCashInvoice(null)
                setPaymentForm({
                  facture_id: '',
                  montant: '',
                  mode_paiement: 'ESPECES',
                })
              }}
            >
              Annuler
            </button>
          </div>
        </form>
      </section>
    )}

    <section className="content-card">
      <div className="card-heading">
        <div>
          <h2>Factures à encaisser</h2>
          <p>{cashInvoices.length} facture(s)</p>
        </div>
      </div>

      {inventoryLoading ? (
        <div className="loading-state">Chargement de la caisse…</div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>FACTURE</th>
                <th>DATE</th>
                <th>CLIENT</th>
                <th>TOTAL</th>
                <th>ENCAISSÉ</th>
                <th>RESTANT</th>
                <th>ÉTAT</th>
                <th>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {cashInvoices.map((invoice) => (
                <tr key={invoice.id}>
                  <td>{invoice.facture_reference}</td>
                  <td>{formatBusinessDate(invoice.date_emission)}</td>
                  <td>{invoice.client_nom || 'Vente comptant'}</td>
                  <td>{Number(invoice.total_facture).toLocaleString('fr-FR')}</td>
                  <td>{Number(invoice.total_encaisse).toLocaleString('fr-FR')}</td>
                  <td>{Number(invoice.solde_restant).toLocaleString('fr-FR')}</td>
                  <td>{invoice.etat_paiement}</td>
                  <td>
                    {Number(invoice.solde_restant) > 0 ? (
                      <button
                        className="primary-button"
                        disabled={Boolean(todayCashClosure?.date_cloture)}
                        onClick={() => {
                          setSelectedCashInvoice(invoice)
                          setPaymentForm({
                            facture_id: String(invoice.id),
                            montant: String(invoice.solde_restant),
                            mode_paiement: 'ESPECES',
                          })
                        }}
                      >
                        Encaisser
                      </button>
                    ) : 'Soldée'}
                  </td>
                </tr>
              ))}

              {!cashInvoices.length && (
                <tr>
                  <td colSpan="8" className="empty-state">
                    Aucune facture à encaisser.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>

    <section className="content-card">
      <div className="card-heading">
        <div>
          <h2>Historique des encaissements</h2>
          <p>{encaissements.length} paiement(s) enregistré(s)</p>
        </div>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>RÉFÉRENCE</th>
              <th>DATE</th>
              <th>FACTURE</th>
              <th>CLIENT</th>
              <th>MONTANT</th>
              <th>MODE</th>
              <th>ENCAISSÉ PAR</th>
              <th>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {encaissements.map((payment) => (
              <tr key={payment.reference}>
                <td>{payment.reference}</td>
                <td>{formatBusinessDateTime(payment.date_encaissement)}</td>
                <td>{payment.facture_reference}</td>
                <td>{payment.client_nom || 'Vente comptant'}</td>
                <td>{Number(payment.montant).toLocaleString('fr-FR')} FCFA</td>
                <td>{payment.mode_paiement_libelle}</td>
                <td>{payment.encaisse_par_nom}</td>
                <td>
                  <div className="inventory-row-actions">
                    <button
                      className="secondary-button"
                      onClick={() => loadReceipt(payment.id)}
                    >
                      Reçu
                    </button>
                    {Number(payment.montant_remboursable) > 0 && (
                      <button
                        className="secondary-button"
                        onClick={() => {
                          setSelectedPaymentForRefund(payment)
                          setRefundForm({
                            montant: payment.montant_remboursable,
                            motif: '',
                            mode_remboursement: payment.mode_paiement,
                          })
                        }}
                      >
                        Demander un remboursement
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}

            {!encaissements.length && (
              <tr>
                <td colSpan="8" className="empty-state">
                  Aucun encaissement enregistré.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>

    {selectedPaymentForRefund && (
      <section className="content-card inventory-form-card">
        <div className="card-heading">
          <div>
            <h2>Demander un remboursement</h2>
            <p>
              Paiement {selectedPaymentForRefund.reference} · Montant
              remboursable : {Number(selectedPaymentForRefund.montant_remboursable).toLocaleString('fr-FR')} FCFA
            </p>
          </div>
        </div>
        <form className="inventory-form" onSubmit={saveRefund}>
          <label>
            Montant demandé (FCFA)
            <input
              type="number"
              min="0.01"
              max={selectedPaymentForRefund.montant_remboursable}
              step="0.01"
              required
              value={refundForm.montant}
              onChange={(event) =>
                setRefundForm({ ...refundForm, montant: event.target.value })
              }
            />
          </label>
          <label>
            Motif obligatoire
            <textarea
              required
              maxLength="1000"
              value={refundForm.motif}
              onChange={(event) =>
                setRefundForm({ ...refundForm, motif: event.target.value })
              }
            />
          </label>
          <label>
            Mode de remboursement prévu
            <select
              value={refundForm.mode_remboursement}
              onChange={(event) =>
                setRefundForm({
                  ...refundForm,
                  mode_remboursement: event.target.value,
                })
              }
            >
              <option value="ESPECES">Espèces</option>
              <option value="MOBILE_MONEY">Mobile Money</option>
              <option value="CARTE">Carte bancaire</option>
              <option value="VIREMENT">Virement</option>
              <option value="AUTRE">Autre</option>
            </select>
          </label>
          <div className="inventory-form-actions inventory-form-wide">
            <button className="primary-button" type="submit" disabled={refundSubmitting}>
              {refundSubmitting ? 'Envoi...' : 'Soumettre pour approbation'}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => setSelectedPaymentForRefund(null)}
              disabled={refundSubmitting}
            >
              Annuler
            </button>
          </div>
        </form>
      </section>
    )}

    <section className="content-card">
      <div className="card-heading">
        <div>
          <h2>Remboursements</h2>
          <p>Tout remboursement reste en attente jusqu'à la décision d'un Administrateur.</p>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>RÉFÉRENCE</th>
              <th>PAIEMENT</th>
              <th>FACTURE / CLIENT</th>
              <th>MONTANT</th>
              <th>MODE / JUSTIFICATIF</th>
              <th>MOTIF</th>
              <th>STATUT</th>
              <th>DEMANDE / DÉCISION / EXÉCUTION</th>
              <th>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {remboursements.map((refund) => (
              <tr key={refund.id}>
                <td>{refund.reference}</td>
                <td>{refund.encaissement_reference}</td>
                <td>{refund.facture_reference} · {refund.client_nom}</td>
                <td>{Number(refund.montant).toLocaleString('fr-FR')} FCFA</td>
                <td>
                  {refund.mode_remboursement_libelle}
                  {refund.reference_execution && (
                    <span className="table-secondary">
                      Réf. {refund.reference_execution}
                    </span>
                  )}
                </td>
                <td>{refund.motif}</td>
                <td>{refund.statut}</td>
                <td>
                  {refund.demande_par_nom}
                  {refund.decide_par_nom && ` · autorisé/refusé par ${refund.decide_par_nom}`}
                  {refund.execute_par_nom && ` · exécuté par ${refund.execute_par_nom}`}
                </td>
                <td>
                  {refund.statut === 'EN_ATTENTE' && canEditStoreSettings ? (
                      <div className="inventory-row-actions">
                        <button
                          className="primary-button"
                          onClick={() => decideRefund(refund.id, 'approuver')}
                        >
                          Autoriser
                        </button>
                        <button
                          className="secondary-button"
                          onClick={() => decideRefund(refund.id, 'refuser')}
                        >
                          Refuser
                        </button>
                      </div>
                  ) : refund.statut === 'AUTORISE' && (
                    currentUser?.is_superuser
                    || currentUser?.roles?.includes('Administrateur')
                    || currentUser?.roles?.includes('Caissier')
                  ) ? (
                    <button
                      className="primary-button"
                      onClick={() => executeRefund(refund)}
                    >
                      Confirmer l'exécution
                    </button>
                  ) : '—'}
                </td>
              </tr>
            ))}
            {!remboursements.length && (
              <tr>
                <td colSpan="9" className="empty-state">
                  Aucune demande de remboursement.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {selectedRefundForExecution && (
        <section className="content-card inventory-form-card">
          <div className="card-heading">
            <div>
              <h2>Confirmer l'exécution · {selectedRefundForExecution.reference}</h2>
              <p>
                Cette confirmation enregistre l'opération financière déjà réalisée;
                elle ne déclenche aucun paiement externe.
              </p>
            </div>
          </div>
          <form className="inventory-form" onSubmit={confirmRefundExecution}>
            <label>
              Référence du justificatif
              <input
                required
                maxLength="100"
                value={refundExecutionReference}
                onChange={(event) => setRefundExecutionReference(event.target.value)}
              />
            </label>
            <div className="inventory-form-actions inventory-form-wide">
              <button className="primary-button" type="submit">
                Enregistrer l'exécution
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => setSelectedRefundForExecution(null)}
              >
                Annuler
              </button>
            </div>
          </form>
        </section>
      )}
    </section>

    {!todayCashClosure?.date_cloture && (
      <section className="content-card">
        <div className="card-heading">
          <div>
            <h2>Clôture quotidienne</h2>
            <p>
              Les montants théoriques proviennent des encaissements et remboursements
              exécutés aujourd'hui. Le comptage physique est facultatif.
            </p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>MODE</th>
                <th>ENCAISSÉ BRUT</th>
                <th>REMBOURSÉ</th>
                <th>THÉORIQUE NET</th>
              </tr>
            </thead>
            <tbody>
              {(cashPreview?.lignes || []).map((line) => (
                <tr key={line.mode_paiement}>
                  <td>{line.mode_paiement_libelle}</td>
                  <td>{Number(line.montant_encaisse).toLocaleString('fr-FR')} FCFA</td>
                  <td>{Number(line.montant_rembourse).toLocaleString('fr-FR')} FCFA</td>
                  <td>{Number(line.montant_theorique).toLocaleString('fr-FR')} FCFA</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="cash-count-grid">
          {[
            ['ESPECES', 'Espèces'],
            ['MOBILE_MONEY', 'Mobile money'],
            ['CARTE', 'Carte bancaire'],
            ['VIREMENT', 'Virement'],
            ['AUTRE', 'Autre'],
          ].map(([mode, label]) => (
            <label key={mode}>
              Comptage réel · {label} (FCFA)
              <input
                type="number"
                min="0"
                step="0.01"
                value={cashCount[mode] || ''}
                onChange={(event) =>
                  setCashCount({ ...cashCount, [mode]: event.target.value })
                }
              />
            </label>
          ))}
        </div>
        <button
          className="primary-button"
          onClick={closeCash}
          disabled={closingCash}
        >
          {closingCash ? 'Clôture...' : 'Clôturer définitivement la journée'}
        </button>
      </section>
    )}

    <section className="content-card">
      <div className="card-heading">
        <div>
          <h2>Historique des clôtures</h2>
          <p>{cloturesCaisse.filter((closure) => closure.date_cloture).length} journée(s) clôturée(s)</p>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>JOURNÉE</th>
              <th>CLÔTURÉE LE</th>
              <th>RESPONSABLE</th>
              <th>MODE DE PAIEMENT</th>
              <th>ENCAISSÉ BRUT</th>
              <th>REMBOURSÉ</th>
              <th>THÉORIQUE</th>
              <th>COMPTÉ</th>
              <th>ÉCART</th>
            </tr>
          </thead>
          <tbody>
            {cloturesCaisse.filter((closure) => closure.date_cloture).flatMap((closure) =>
              closure.lignes.map((line) => (
                <tr key={`${closure.id}-${line.mode_paiement}`}>
                  <td>{formatBusinessDate(closure.date_jour)}</td>
                  <td>{formatBusinessDateTime(closure.date_cloture)}</td>
                  <td>{closure.cloturee_par_nom}</td>
                  <td>{line.mode_paiement_libelle}</td>
                  <td>{Number(line.montant_encaisse).toLocaleString('fr-FR')} FCFA</td>
                  <td>{Number(line.montant_rembourse).toLocaleString('fr-FR')} FCFA</td>
                  <td>{Number(line.montant_theorique).toLocaleString('fr-FR')} FCFA</td>
                  <td>{line.montant_compte === null ? 'Non renseigné' : `${Number(line.montant_compte).toLocaleString('fr-FR')} FCFA`}</td>
                  <td>{line.ecart === null ? '—' : `${Number(line.ecart).toLocaleString('fr-FR')} FCFA`}</td>
                </tr>
              )),
            )}
            {!cloturesCaisse.some((closure) => closure.date_cloture) && (
              <tr>
                <td colSpan="9" className="empty-state">
                  Aucune clôture enregistrée.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  </>
            )
          )}

          {page === 'factures' && (
            <>
              <div className="page-heading non-printable">
                <div>
                  <div className="eyebrow">DOCUMENTS COMMERCIAUX</div>
                  <h1>Factures</h1>
                  <p>Factures émises à partir des ventes validées.</p>
                </div>
                <button
                  className="primary-button"
                  onClick={loadInvoices}
                  disabled={inventoryLoading}
                >
                  Actualiser
                </button>
              </div>

              {inventoryError && (
                <div className="error-message non-printable" role="alert">
                  {inventoryError}
                </div>
              )}

              {selectedInvoiceId ? (
                (() => {
                  const invoice = invoices.find((item) => item.id === selectedInvoiceId)
                  if (!invoice) return null
                  return (
                    <section className="invoice-print-area">
                      <div className="invoice-actions non-printable">
                        <button
                          className="secondary-button"
                          onClick={() => setSelectedInvoiceId(null)}
                        >
                          Retour aux factures
                        </button>
                        <button
                          className="primary-button"
                          onClick={() => window.print()}
                        >
                          Imprimer / PDF
                        </button>
                      </div>
                      <article className="invoice-paper">
                        <header className="invoice-heading">
                          <div>
                            {storeSettings?.logo && (
                              <img
                                className="invoice-store-logo"
                                src={storeSettings.logo}
                                alt={`Logo ${storeSettings.nom_magasin}`}
                              />
                            )}
                            <strong>
                              {storeSettings?.nom_magasin}
                            </strong>
                            {storeSettings?.adresse && <p>{storeSettings.adresse}</p>}
                            {storeSettings?.telephone && <p>{storeSettings.telephone}</p>}
                            {storeSettings?.email && <p>{storeSettings.email}</p>}
                          </div>
                          <div className="invoice-number">
                            <span>FACTURE</span>
                            <strong>{invoice.reference}</strong>
                          </div>
                        </header>
                        <div className="invoice-meta">
                          <p><span>Date d'émission</span>{formatBusinessDate(invoice.date_emission)}</p>
                          <p><span>Référence vente</span>{invoice.vente_reference}</p>
                          <p><span>Client</span>{invoice.client_nom || 'Vente comptant'}</p>
                        </div>
                        <div className="table-scroll">
                          <table className="invoice-lines">
                            <thead>
                              <tr>
                                <th>RÉFÉRENCE</th>
                                <th>DÉSIGNATION</th>
                                <th>QUANTITÉ</th>
                                <th>PRIX UNITAIRE</th>
                                <th>TOTAL</th>
                              </tr>
                            </thead>
                            <tbody>
                              {invoice.lignes.map((line) => (
                                <tr key={line.id}>
                                  <td>{line.reference_piece}</td>
                                  <td>{line.designation}</td>
                                  <td>{line.quantite}</td>
                                  <td>{Number(line.prix_unitaire).toLocaleString('fr-FR')}</td>
                                  <td>{Number(line.total).toLocaleString('fr-FR')}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="invoice-grand-total">
                          <span>Total</span>
                          <strong>{Number(invoice.total).toLocaleString('fr-FR')}</strong>
                        </div>
                        <div className="invoice-payment-summary">
                          <p><span>Encaissé avant remboursements</span><strong>{Number(invoice.montant_encaisse_brut).toLocaleString('fr-FR')} FCFA</strong></p>
                          <p><span>Remboursé</span><strong>{Number(invoice.montant_rembourse).toLocaleString('fr-FR')} FCFA</strong></p>
                          <p><span>Net payé</span><strong>{Number(invoice.total_encaisse).toLocaleString('fr-FR')} FCFA</strong></p>
                          <p><span>Solde restant</span><strong>{Number(invoice.solde_restant).toLocaleString('fr-FR')} FCFA</strong></p>
                          <p><span>État du paiement</span><strong>{invoice.etat_paiement}</strong></p>
                        </div>
                        {invoice.historique_encaissements?.length > 0 && (
                          <section className="invoice-payment-history">
                            <h2>Historique des règlements</h2>
                            <div className="table-scroll">
                              <table className="invoice-lines">
                                <thead>
                                  <tr>
                                    <th>RÉFÉRENCE</th>
                                    <th>DATE</th>
                                    <th>MONTANT</th>
                                    <th>MODE</th>
                                    <th>ENCAISSÉ PAR</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {invoice.historique_encaissements.map((payment) => (
                                    <tr key={payment.id}>
                                      <td>{payment.reference}</td>
                                      <td>{formatBusinessDateTime(payment.date_encaissement)}</td>
                                      <td>{Number(payment.montant).toLocaleString('fr-FR')} FCFA</td>
                                      <td>{payment.mode_paiement_libelle}</td>
                                      <td>{payment.encaisse_par_nom}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </section>
                        )}
                        <footer className="invoice-footer">
                          {storeSettings?.pied_de_page && (
                            <p>{storeSettings.pied_de_page}</p>
                          )}
                          Émise par {invoice.emise_par_nom}
                        </footer>
                      </article>
                    </section>
                  )
                })()
              ) : (
                <section className="content-card">
                  <div className="card-heading">
                    <div>
                      <h2>Factures émises</h2>
                      <p>{invoices.length} facture(s)</p>
                    </div>
                  </div>
                  {inventoryLoading ? (
                    <div className="loading-state">Chargement des factures…</div>
                  ) : (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>FACTURE</th>
                            <th>DATE</th>
                            <th>VENTE</th>
                            <th>CLIENT</th>
                            <th>TOTAL</th>
                            <th>ACTION</th>
                          </tr>
                        </thead>
                        <tbody>
                          {invoices.map((invoice) => (
                            <tr key={invoice.id}>
                              <td>{invoice.reference}</td>
                              <td>{formatBusinessDate(invoice.date_emission)}</td>
                              <td>{invoice.vente_reference}</td>
                              <td>{invoice.client_nom || 'Vente comptant'}</td>
                              <td>{Number(invoice.total).toLocaleString('fr-FR')}</td>
                              <td>
                                <button
                                  className="secondary-button"
                                  onClick={() => setSelectedInvoiceId(invoice.id)}
                                >
                                  Consulter
                                </button>
                              </td>
                            </tr>
                          ))}
                          {!invoices.length && !inventoryLoading && (
                            <tr>
                              <td colSpan="6" className="empty-state">
                                Aucune facture émise.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              )}
            </>
          )}
          {page === 'caisse' && !canAccessCash && (
            <section className="content-card" role="alert">
              <div className="card-heading">
                <div>
                  <h2>Accès non autorisé</h2>
                  <p>La caisse est réservée à l’Administrateur et au Caissier.</p>
                </div>
              </div>
            </section>
          )}

          {page === 'utilisateurs' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">ADMINISTRATION</div>
                  <h1>Utilisateurs et rôles</h1>
                  <p>
                    Consulte les comptes et les rôles associés à chaque
                    utilisateur.
                  </p>
                </div>
                <button
                  className="primary-button"
                  onClick={loadUsers}
                  disabled={loading}
                >
                  <span>↻</span> {loading ? 'Actualisation…' : 'Actualiser'}
                </button>
              </div>

              {error && (
                <div className="error-message" role="alert">
                  <strong>Opération impossible</strong>
                  <p>{error}</p>
                </div>
              )}

              <section className="content-card inventory-form-card">
                <div className="card-heading">
                  <div>
                    <h2>{editingUserId ? 'Modifier le compte' : 'Créer un compte'}</h2>
                    <p>Les rôles disponibles proviennent des groupes Django existants.</p>
                  </div>
                </div>
                <form className="inventory-form" onSubmit={saveUser}>
                  <label>
                    Nom d'utilisateur
                    <input
                      required
                      maxLength="150"
                      autoComplete="off"
                      value={userForm.username}
                      onChange={(event) =>
                        setUserForm({ ...userForm, username: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Prénom
                    <input
                      value={userForm.first_name}
                      onChange={(event) =>
                        setUserForm({ ...userForm, first_name: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Nom
                    <input
                      value={userForm.last_name}
                      onChange={(event) =>
                        setUserForm({ ...userForm, last_name: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    Adresse e-mail
                    <input
                      type="email"
                      value={userForm.email}
                      onChange={(event) =>
                        setUserForm({ ...userForm, email: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    {editingUserId ? 'Nouveau mot de passe (facultatif)' : 'Mot de passe'}
                    <input
                      type="password"
                      required={!editingUserId}
                      autoComplete="new-password"
                      value={userForm.mot_de_passe}
                      onChange={(event) =>
                        setUserForm({ ...userForm, mot_de_passe: event.target.value })
                      }
                    />
                  </label>
                  <fieldset className="role-fieldset inventory-form-wide">
                    <legend>Rôles</legend>
                    {availableRoles.length ? (
                      <div className="role-checkboxes">
                        {availableRoles.map((role) => (
                          <label key={role.id}>
                            <input
                              type="checkbox"
                              checked={userForm.roles.includes(role.name)}
                              onChange={(event) =>
                                setUserForm({
                                  ...userForm,
                                  roles: event.target.checked
                                    ? [...userForm.roles, role.name]
                                    : userForm.roles.filter((name) => name !== role.name),
                                })
                              }
                            />
                            {roleLabels[role.name] || role.name}
                          </label>
                        ))}
                      </div>
                    ) : (
                      <p className="form-hint">
                        Aucun groupe de rôle n’existe encore. Crée-les dans
                        l’administration Django avant d’attribuer des rôles.
                      </p>
                    )}
                  </fieldset>
                  <div className="inventory-form-actions inventory-form-wide">
                    <button className="primary-button" type="submit">
                      {editingUserId ? 'Enregistrer' : 'Créer le compte'}
                    </button>
                    {editingUserId && (
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => {
                          setEditingUserId(null)
                          setUserForm(emptyUserForm)
                        }}
                      >
                        Annuler
                      </button>
                    )}
                  </div>
                </form>
              </section>

              {passwordResetUser && (
                <section className="content-card admin-password-reset">
                  <div className="card-heading">
                    <div>
                      <h2>Réinitialiser le mot de passe</h2>
                      <p>
                        Nouveau mot de passe pour @{passwordResetUser.username}.
                        Il ne sera jamais affiché après enregistrement.
                      </p>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setPasswordResetUser(null)
                        setAdminPasswordForm({ new_password: '', confirm_password: '' })
                        setAdminPasswordError('')
                        setAdminPasswordSuccess('')
                      }}
                    >
                      Fermer
                    </button>
                  </div>
                  {adminPasswordError && (
                    <div className="error-message" role="alert">
                      {adminPasswordError}
                    </div>
                  )}
                  {adminPasswordSuccess && (
                    <div className="success-message" role="status">
                      {adminPasswordSuccess}
                    </div>
                  )}
                  <form className="inventory-form" onSubmit={resetUserPassword}>
                    <label>
                      Nouveau mot de passe
                      <input
                        type="password"
                        autoComplete="new-password"
                        required
                        value={adminPasswordForm.new_password}
                        onChange={(event) => setAdminPasswordForm({
                          ...adminPasswordForm,
                          new_password: event.target.value,
                        })}
                      />
                    </label>
                    <label>
                      Confirmer le mot de passe
                      <input
                        type="password"
                        autoComplete="new-password"
                        required
                        value={adminPasswordForm.confirm_password}
                        onChange={(event) => setAdminPasswordForm({
                          ...adminPasswordForm,
                          confirm_password: event.target.value,
                        })}
                      />
                    </label>
                    <div className="inventory-form-actions inventory-form-wide">
                      <button
                        className="primary-button"
                        type="submit"
                        disabled={adminPasswordSaving}
                      >
                        {adminPasswordSaving ? 'Réinitialisation…' : 'Réinitialiser'}
                      </button>
                    </div>
                  </form>
                </section>
              )}

              <section className="content-card">
                <div className="card-heading">
                  <div>
                    <h2>Permissions effectives par rôle</h2>
                    <p>
                      Droits métier appliqués par les APIs selon les rôles attribués.
                    </p>
                  </div>
                </div>
                <div className="role-permission-note">
                  Le statut technique « staff » n’accorde aucun droit métier. Les opérations sensibles restent contrôlées par rôle.
                </div>
                <div className="table-scroll">
                  <table className="role-permission-table">
                    <thead>
                      <tr>
                        <th>RÔLE</th>
                        {rolePermissionModules.map(([key, label]) => (
                          <th key={key}>{label.toUpperCase()}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {effectiveRolePermissions.map((role) => (
                        <tr key={role.id}>
                          <td>
                            <strong>{roleLabels[role.name] || role.name}</strong>
                            <details className="django-permission-details">
                              <summary>Permissions Django</summary>
                              {role.permissions_django.length ? (
                                <ul>
                                  {role.permissions_django.map((permission) => (
                                    <li key={`${permission.app_label}.${permission.codename}`}>
                                      {permission.app_label}: {permission.name}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <span>Aucune permission Django de groupe attribuée.</span>
                              )}
                            </details>
                          </td>
                          {rolePermissionModules.map(([key]) => (
                            <td key={key}>
                              <span className={`permission-level level-${role.permissions_api[key]}`}>
                                {permissionLabels[role.permissions_api[key]] || role.permissions_api[key]}
                              </span>
                            </td>
                          ))}
                        </tr>
                      ))}
                      {!effectiveRolePermissions.length && !loading && (
                        <tr>
                          <td colSpan={rolePermissionModules.length + 1} className="empty-state">
                            Aucun groupe trouvé.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="stats-grid user-stats">
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Total utilisateurs</span>
                    <span className="stat-icon blue">♙</span>
                  </div>
                  <strong className="stat-number">{users.length}</strong>
                  <span className="stat-note">Comptes enregistrés</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Comptes actifs</span>
                    <span className="stat-icon green">✓</span>
                  </div>
                  <strong className="stat-number">{activeUsers}</strong>
                  <span className="stat-note">Autorisés à se connecter</span>
                </article>
                <article className="stat-card">
                  <div className="stat-top">
                    <span>Comptes inactifs</span>
                    <span className="stat-icon orange">⊘</span>
                  </div>
                  <strong className="stat-number">
                    {users.length - activeUsers}
                  </strong>
                  <span className="stat-note">Accès désactivés</span>
                </article>
              </section>

              <section className="content-card">
                <div className="card-heading users-card-heading">
                  <div>
                    <h2>Liste des utilisateurs</h2>
                    <p>
                      {users.length} compte{users.length > 1 ? 's' : ''}{' '}
                      trouvé{users.length > 1 ? 's' : ''}
                      {lastUpdate &&
                        ` · Mis à jour à ${lastUpdate.toLocaleTimeString(
                          'fr-FR',
                          { hour: '2-digit', minute: '2-digit' },
                        )}`}
                    </p>
                  </div>
                  <label className="search-box">
                    <span>⌕</span>
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Rechercher un utilisateur..."
                    />
                  </label>
                </div>

                {error && (
                  <div className="error-message">
                    <strong>Chargement impossible</strong>
                    <p>{error}</p>
                    <button onClick={loadUsers}>Réessayer</button>
                  </div>
                )}

                {loading && (
                  <div className="loading-state">
                    Chargement des utilisateurs…
                  </div>
                )}

                {!loading && !error && (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>UTILISATEUR</th>
                          <th>ADRESSE E-MAIL</th>
                          <th>RÔLE(S)</th>
                          <th>STATUT</th>
                          <th>ACTIONS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredUsers.map((user) => (
                          <tr key={user.id}>
                            <td>
                              <div className="user-cell">
                                <div className="user-avatar">
                                  {(
                                    user.first_name?.[0] ||
                                    user.username?.[0] ||
                                    'U'
                                  ).toUpperCase()}
                                </div>
                                <div>
                                  <strong>
                                    {[user.first_name, user.last_name]
                                      .filter(Boolean)
                                      .join(' ') || user.username}
                                  </strong>
                                  <small>@{user.username}</small>
                                </div>
                              </div>
                            </td>
                            <td>{user.email || 'Non renseignée'}</td>
                            <td>
                              <div className="role-list">
                                {(user.roles || []).length ? (
                                  user.roles.map((role) => (
                                    <span className="role-tag" key={role}>
                                      {roleLabels[role] || role}
                                    </span>
                                  ))
                                ) : (
                                  <span className="no-role">
                                    Aucun rôle attribué
                                  </span>
                                )}
                              </div>
                            </td>
                            <td>
                              <span
                                className={`status-pill ${
                                  user.is_active ? 'enabled' : 'disabled'
                                }`}
                              >
                                <span />
                                {user.is_active ? 'Actif' : 'Inactif'}
                              </span>
                            </td>
                            <td>
                              <div className="inventory-row-actions">
                                <button
                                  className="secondary-button"
                                  onClick={() => editUser(user)}
                                >
                                  Modifier
                                </button>
                                <button
                                  className="secondary-button"
                                  onClick={() => toggleUserStatus(user)}
                                  disabled={user.id === currentUser.id}
                                  title={
                                    user.id === currentUser.id
                                      ? 'Tu ne peux pas désactiver ton propre compte.'
                                      : undefined
                                  }
                                >
                                  {user.is_active ? 'Désactiver' : 'Réactiver'}
                                </button>
                                {user.id !== currentUser.id && (
                                  <button
                                    className="secondary-button"
                                    onClick={() => {
                                      setPasswordResetUser(user)
                                      setAdminPasswordForm({
                                        new_password: '',
                                        confirm_password: '',
                                      })
                                      setAdminPasswordError('')
                                      setAdminPasswordSuccess('')
                                    }}
                                  >
                                    Réinitialiser le mot de passe
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                        {filteredUsers.length === 0 && (
                          <tr>
                            <td colSpan="5" className="empty-state">
                              Aucun utilisateur correspondant à la recherche.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="table-footer">
                  <span>
                    Affichage de {filteredUsers.length} utilisateur(s)
                  </span>
                  <span>Source : API Django</span>
                </div>
              </section>

              <div className="info-note">
                <span>ⓘ</span>
                <p>
                  Seuls les administrateurs peuvent créer des comptes et leur attribuer les rôles définis dans Django.
                </p>
              </div>
            </>
          )}
          
{page === 'parametres-magasin' && (
  <>
    <div className="page-heading store-settings-heading">
      <div className="store-settings-heading-icon" aria-hidden="true">⚙</div>
      <div>
        <div className="eyebrow">ADMINISTRATION</div>
        <h1>Paramètres du magasin</h1>
        <p>Personnalisez l’identité qui apparaît sur vos factures et reçus.</p>
      </div>
      <span className={`store-settings-access ${canEditStoreSettings ? 'is-editable' : ''}`}>
        {canEditStoreSettings ? 'Modification autorisée' : 'Consultation seule'}
      </span>
    </div>

    {storeSettingsError && (
      <div className="error-message" role="alert">
        {storeSettingsError}
      </div>
    )}

    {storeSettingsSuccess && (
      <div className="success-message" role="status">
        {storeSettingsSuccess}
      </div>
    )}

    {storeSettingsLoading ? (
      <section className="content-card">
        Chargement des paramètres...
      </section>
    ) : storeSettings && (
      <>
        {!canEditStoreSettings && (
          <div className="info-note">
            <span>ⓘ</span>
            <p>
              Vous pouvez consulter les informations du magasin.
              Seul l'Administrateur peut les modifier.
            </p>
          </div>
        )}

        <section className="content-card store-identity-card">
          <div className="section-heading">
            <div>
              <h2>Identité du magasin</h2>
              <p>Ces informations apparaîtront sur les documents commerciaux.</p>
            </div>
          </div>

          <div className="form-grid">
            <div className="store-identity-preview">
              <div className="store-preview-logo">
                {storeSettings.logo ? (
                  <img
                    src={storeSettings.logo}
                    alt={`Logo ${storeSettings.nom_magasin || 'du magasin'}`}
                  />
                ) : (
                  <span aria-hidden="true">PA</span>
                )}
              </div>
              <div>
                <span className="store-preview-label">APERÇU DOCUMENT</span>
                <strong>{storeSettings.nom_magasin || 'Nom de votre magasin'}</strong>
                <span>{storeSettings.adresse || 'Adresse du magasin'}</span>
                <span>{storeSettings.telephone || 'Téléphone'}</span>
              </div>
            </div>

            <div className="form-group">
              <label>Nom du magasin</label>
              <input
                type="text"
                value={storeSettings.nom_magasin || ''}
                disabled={!canEditStoreSettings}
                onChange={(e) =>
                  setStoreSettings({
                    ...storeSettings,
                    nom_magasin: e.target.value,
                  })
                }
              />
            </div>

            <div className="form-group">
              <label>Adresse</label>
              <input
                type="text"
                value={storeSettings.adresse || ''}
                disabled={!canEditStoreSettings}
                onChange={(e) =>
                  setStoreSettings({
                    ...storeSettings,
                    adresse: e.target.value,
                  })
                }
              />
            </div>

            <div className="form-group">
              <label>Téléphone</label>
              <input
                type="text"
                value={storeSettings.telephone || ''}
                disabled={!canEditStoreSettings}
                onChange={(e) =>
                  setStoreSettings({
                    ...storeSettings,
                    telephone: e.target.value,
                  })
                }
              />
            </div>

            <div className="form-group">
              <label>Adresse e-mail</label>
              <input
                type="email"
                value={storeSettings.email || ''}
                disabled={!canEditStoreSettings}
                onChange={(e) =>
                  setStoreSettings({
                    ...storeSettings,
                    email: e.target.value,
                  })
                }
              />
            </div>

            <div className="form-group">
              <label>Logo du magasin</label>
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.webp"
                disabled={!canEditStoreSettings}
                onChange={(event) => {
                  const file = event.target.files?.[0] || null
                  if (file && file.size > 2 * 1024 * 1024) {
                    setStoreLogoFile(null)
                    setStoreSettingsError('Le logo ne doit pas dépasser 2 Mo.')
                    return
                  }
                  if (file && !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
                    setStoreLogoFile(null)
                    setStoreSettingsError('Formats autorisés : PNG, JPEG ou WebP.')
                    return
                  }
                  setStoreSettingsError('')
                  setStoreLogoFile(file)
                }}
              />
              {storeSettings.logo && (
                <div className="store-logo-preview">
                  <img
                    src={storeSettings.logo}
                    alt="Logo du magasin"
                    style={{ maxWidth: '150px', maxHeight: '100px', objectFit: 'contain' }}
                  />
                </div>
              )}
              {storeLogoFile && (
                <small>Fichier sélectionné : {storeLogoFile.name}</small>
              )}
            </div>
          </div>
        </section>

        <section className="content-card store-footer-card">
          <div className="section-heading">
            <div>
              <h2>Message de pied de page</h2>
              <p>Une formule courte affichée en bas des factures et des reçus.</p>
            </div>
            <span className="store-footer-count">
              {(storeSettings.pied_de_page || '').length} caractères
            </span>
          </div>
          <div className="form-group">
            <label htmlFor="store-footer">Texte du pied de page</label>
            <textarea
              id="store-footer"
              rows="4"
              value={storeSettings.pied_de_page || ''}
              disabled={!canEditStoreSettings}
              onChange={(e) =>
                setStoreSettings({
                  ...storeSettings,
                  pied_de_page: e.target.value,
                })
              }
              placeholder="Exemple : Merci pour votre confiance."
            />
            <small className="store-footer-hint">
              {storeSettings.pied_de_page
                ? `Aperçu : « ${storeSettings.pied_de_page} »`
                : 'Sans texte, aucun message ne sera ajouté aux documents.'}
            </small>
          </div>
        </section>

        {canEditStoreSettings && (
          <div className="form-actions store-settings-save-bar">
            <span>Vos changements seront repris sur les prochains documents générés.</span>
            <button
              type="button"
              className="primary-button"
              onClick={saveStoreSettings}
              disabled={storeSettingsSaving}
            >
              {storeSettingsSaving ? 'Enregistrement...' : 'Enregistrer les paramètres'}
            </button>
          </div>
        )}
      </>
    )}
  </>
)}

          {page !== 'dashboard' && page !== 'rapports'&& page !== 'parametres-magasin'&& page !== 'caisse' && page !== 'pieces' && page !== 'stock' && page !== 'clients' && page !== 'fournisseurs' && page !== 'ventes' && page !== 'factures' && page !== 'utilisateurs' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">GESTION DU MAGASIN</div>
                  <h1>{navigation.find((item) => item.id === page)?.label}</h1>
                  <p>Cette rubrique sera intégrée progressivement.</p>
                </div>
              </div>
              <section className="content-card coming-soon">
                <div className="coming-icon">⚙</div>
                <h2>Module en préparation</h2>
                <p>
                  Nous allons connecter cette rubrique à la base de données
                  Django sans supprimer les informations existantes.
                </p>
                <button
                  className="primary-button"
                  onClick={() => setPage('dashboard')}
                >
                  Retour au tableau de bord
                </button>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
