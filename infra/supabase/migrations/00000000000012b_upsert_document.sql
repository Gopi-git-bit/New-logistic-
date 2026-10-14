CREATE OR REPLACE FUNCTION public.upsert_order_document(
    p_order_id UUID, p_doc_type TEXT, p_image_url TEXT DEFAULT NULL,
    p_ocr_raw_text TEXT DEFAULT NULL, p_ocr_confidence NUMERIC DEFAULT NULL,
    p_ocr_provider TEXT DEFAULT NULL, p_uploaded_by UUID DEFAULT NULL
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE v_id UUID;
BEGIN
    INSERT INTO public.order_documents
        (order_id, document_type, image_url, ocr_raw_text,
         ocr_confidence, ocr_provider, uploaded_by)
    VALUES (p_order_id, p_doc_type, p_image_url, p_ocr_raw_text,
            p_ocr_confidence, p_ocr_provider, p_uploaded_by)
    RETURNING document_id INTO v_id;
    RETURN v_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_order_document(UUID,TEXT,TEXT,TEXT,NUMERIC,TEXT,UUID) TO service_role;
