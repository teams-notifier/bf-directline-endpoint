SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: update_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
   IF row(NEW.*) IS DISTINCT FROM row(OLD.*) THEN
      NEW.updated_at = now();
      RETURN NEW;
   ELSE
      RETURN OLD;
   END IF;
END;
$$;


--
-- Name: uuid_generate_v7(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.uuid_generate_v7() RETURNS uuid
    LANGUAGE plpgsql PARALLEL SAFE
    AS $$
  DECLARE
    -- The current UNIX timestamp in milliseconds
    unix_time_ms CONSTANT bytea NOT NULL DEFAULT substring(int8send((extract(epoch FROM clock_timestamp()) * 1000)::bigint) from 3);

    -- The buffer used to create the UUID, starting with the UNIX timestamp and followed by random bytes
    buffer                bytea NOT NULL DEFAULT unix_time_ms || gen_random_bytes(10);
  BEGIN
    -- Set most significant 4 bits of 7th byte to 7 (for UUID v7), keeping the last 4 bits unchanged
    buffer = set_byte(buffer, 6, (b'0111' || get_byte(buffer, 6)::bit(4))::bit(8)::int);

    -- Set most significant 2 bits of 9th byte to 2 (the UUID variant specified in RFC 4122), keeping the last 6 bits unchanged
    buffer = set_byte(buffer, 8, (b'10'   || get_byte(buffer, 8)::bit(6))::bit(8)::int);

    RETURN encode(buffer, 'hex');
  END
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: aadoid_to_tid; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aadoid_to_tid (
    aad_oid uuid NOT NULL,
    tenant_id character varying NOT NULL,
    teams_id character varying NOT NULL,
    name character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone
);


--
-- Name: conversation_reference; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_reference (
    conversation_reference_id bigint NOT NULL,
    tenant_id uuid NOT NULL,
    conversation_teams_id character varying NOT NULL,
    requester_aadoid uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone,
    conversation_reference jsonb,
    activity_reference jsonb
);


--
-- Name: COLUMN conversation_reference.conversation_teams_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.conversation_reference.conversation_teams_id IS 'teams conversation id, unbounded lenght';


--
-- Name: conversation_reference_conversation_reference_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.conversation_reference ALTER COLUMN conversation_reference_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.conversation_reference_conversation_reference_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: conversation_token; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversation_token (
    conversation_token_id bigint NOT NULL,
    conversation_token uuid DEFAULT public.uuid_generate_v7() NOT NULL,
    conversation_reference_id bigint NOT NULL,
    user_description character varying DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone
);


--
-- Name: conversation_token_conversation_token_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.conversation_token ALTER COLUMN conversation_token_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.conversation_token_conversation_token_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: message; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message (
    message_id uuid DEFAULT public.uuid_generate_v7() NOT NULL,
    conversation_token_id bigint NOT NULL,
    conversation_reference_id bigint NOT NULL,
    activity_id character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone,
    deleted_at timestamp with time zone
);


--
-- Name: msg_to_delete; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.msg_to_delete (
    id bigint NOT NULL,
    conv_id character varying NOT NULL,
    activity_id character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: msg_to_delete_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.msg_to_delete ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.msg_to_delete_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying(128) NOT NULL
);


--
-- Name: aadoid_to_tid aadoid_to_tid_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aadoid_to_tid
    ADD CONSTRAINT aadoid_to_tid_pkey PRIMARY KEY (aad_oid);


--
-- Name: conversation_reference conversation_reference_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_reference
    ADD CONSTRAINT conversation_reference_pk PRIMARY KEY (conversation_reference_id);


--
-- Name: conversation_reference conversation_reference_tenant_conv_teams_id_req_aadoid_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_reference
    ADD CONSTRAINT conversation_reference_tenant_conv_teams_id_req_aadoid_uniq UNIQUE (tenant_id, conversation_teams_id, requester_aadoid);


--
-- Name: conversation_token conversation_token_id_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_token
    ADD CONSTRAINT conversation_token_id_uniq PRIMARY KEY (conversation_token_id);


--
-- Name: conversation_token conversation_token_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_token
    ADD CONSTRAINT conversation_token_uniq UNIQUE (conversation_token);


--
-- Name: message message_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message
    ADD CONSTRAINT message_pkey PRIMARY KEY (message_id);


--
-- Name: msg_to_delete msg_to_delete_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.msg_to_delete
    ADD CONSTRAINT msg_to_delete_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: aadoid_to_tid update_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_updated_at BEFORE UPDATE ON public.aadoid_to_tid FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();


--
-- Name: conversation_reference update_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_updated_at BEFORE UPDATE ON public.conversation_reference FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();


--
-- Name: conversation_token update_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_updated_at BEFORE UPDATE ON public.conversation_token FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();


--
-- Name: conversation_token conversation_token_conversation_reference_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversation_token
    ADD CONSTRAINT conversation_token_conversation_reference_id_fkey FOREIGN KEY (conversation_reference_id) REFERENCES public.conversation_reference(conversation_reference_id);


--
-- PostgreSQL database dump complete
--


--
-- Dbmate schema migrations
--
