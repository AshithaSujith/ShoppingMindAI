export type Product = {
  store?: string
  productname?: string
  title?: string
  priceinr?: number
  originalprice?: number
  discountpercent?: number
  productlink?: string
  url?: string
  image?: string
  rating?: number
  reviewcount?: number
  deliverylabel?: string
  isbestprice?: boolean
  isreliable?: boolean
}

export type CanonicalProduct = Record<string, unknown>

export type RecommendationQuestion = {
  question: string
  options: string[]
}

export type Chip = {
  label: string
  value?: string
}

export type Recommendation = {
  title: string
  reason?: string
}

export type Comparison = {
  title?: string
  products?: Product[]
}

export type Card = {
  type: string
  title?: string
  description?: string
  options?: string[]
  groups?: {
    name: string
    options: string[]
  }[]
  submit_button?: string
}

export type Message = {
  role: "user" | "assistant"
  content: string
  cards?: Card[]
  options?: string[]
  optionUsed?: boolean

  products?: Product[]

  searchQuery?: string

  filters?: Record<string, string[]>

  canonicalProduct?: CanonicalProduct

  parsedSearchQuery?: string

  questions?: RecommendationQuestion[]

  chips?: Chip[]

  recommendations?: Recommendation[]

  comparison?: Comparison

  productLine?: string

  confidence?: "low" | "medium" | "high"

  nextAction?: string

  followUps?: string[]
}

export type SessionEntry = {
  query: string
  messages: Message[]
  filters: Record<string, unknown>
}

export type BackendResponse = {
  data?: {
    type?: string

    message?: string
    cards?: Card[]
    assistant_message?: string

    options?: string[]

    questions?: RecommendationQuestion[]

    chips?: Chip[]

    recommendations?: Recommendation[]

    comparison?: Comparison

    product_line?: string

    confidence?: "low" | "medium" | "high"

    next_action?: string

    follow_ups?: string[]

    missing_required_attributes?: string[]

    products?: Product[]

    search_query?: string
    searchquery?: string
    searchQuery?: string

    filters?: Record<string, string[]>

    canonical_product?: CanonicalProduct
    canonicalproduct?: CanonicalProduct
    canonicalProduct?: CanonicalProduct

    parsedsearchquery?: string
    parsedSearchQuery?: string
  }

  message?: string
}

export type SearchRequest = {
  query: string
  session_id: string
}

export type ScrapeRequest = {
  search_query: string
  canonical_product: CanonicalProduct
}